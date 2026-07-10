import axios from 'axios';
import type {
  Project, Instrument, TimeSlot, DashboardData, UtilizationStats,
  DAGData, InsertCost, Task, CapabilityReq, InstrumentFault,
} from '@/types';

export type {
  Project, Instrument, TimeSlot, DashboardData, UtilizationStats,
  DAGData, InsertCost, Task, CapabilityReq, InstrumentFault,
}


const api = axios.create({ baseURL: '/api/v1' });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  r => r,
  error => {
    if (error && error.response && error.response.status === 401) {
      const currentPath = window.location.pathname
      if (currentPath !== '/login') {
        console.warn('[Auth] 401 on', error.config?.url, '- redirecting to login')
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        // Use location.href for hard redirect to clear all state
        window.location.href = '/login?expired=1'
      }
    }
    return Promise.reject(error)
  }
)



// Projects
export const getProjects = (): Promise<Project[]> =>
  api.get<Project[]>('/projects').then(r => r.data);

export const createProject = (data: Partial<Project>): Promise<Project> =>
  api.post<Project>('/projects', data).then(r => r.data);

export const updateProject = (id: number, data: Partial<Project>): Promise<Project> =>
  api.put<Project>(`/projects/${id}`, data).then(r => r.data);

export const getProject = (id: number): Promise<Project> =>
  api.get<Project>(`/projects/${id}`).then(r => r.data);

export const deleteProject = (id: number): Promise<void> =>
  api.delete(`/projects/${id}`)

export const getProjectDAG = (id: number): Promise<DAGData> =>
  api.get<DAGData>(`/projects/${id}/dag`).then(r => r.data);

export const addTask = (projId: number, data: {
  name: string; task_type: string; requires_instrument: boolean;
  est_duration_hours: number; switchover_hours: number;
  predecessor_ids: number[]; instrument_ids: number[];
}): Promise<Task> =>
  api.post<Task>(`/projects/${projId}/tasks`, data).then(r => r.data);


export const deleteTask = (id: number): Promise<void> =>
  api.delete(`/projects/tasks/${id}`)

export const updateTask = (taskId: number, data: {
  name: string; task_type: string; requires_instrument: boolean;
  est_duration_hours: number; switchover_hours: number;
  predecessor_ids: number[]; instrument_ids: number[];
}): Promise<Task> =>
  api.put<Task>(`/projects/tasks/${taskId}`, data).then(r => r.data);

// Instruments
export interface InstrumentQuery {
  include_unavailable?: boolean
}

export const getInstruments = (params?: InstrumentQuery): Promise<Instrument[]> =>
  api.get<Instrument[]>('/instruments', { params }).then(r => r.data);

export interface InstrumentPayload {
  code: string
  name: string
  instrument_group: string
  brand?: string
  model?: string
  location?: string
  availability_status: 'available' | 'unavailable'
  buffer_rate: number
  switchover_base_hours: number
  capabilities: { tag_name: string; tag_value: string }[]
}

export const createInstrument = (data: InstrumentPayload): Promise<Instrument> =>
  api.post<Instrument>('/instruments', data).then(r => r.data);

export const updateInstrument = (id: number, data: InstrumentPayload): Promise<Instrument> =>
  api.put<Instrument>(`/instruments/${id}`, data).then(r => r.data);

export const deleteInstrument = (id: number): Promise<void> =>
  api.delete(`/instruments/${id}`);

export interface InstrumentFaultRequest {
  description: string
  estimated_resolved_at: string
  resolved_at?: string | null
}

export const reportInstrumentFault = (instId: number, data: InstrumentFaultRequest): Promise<InstrumentFault> =>
  api.post<InstrumentFault>(`/instruments/${instId}/fault`, data).then(r => r.data)

export const getOpenInstrumentFaults = (): Promise<InstrumentFault[]> =>
  api.get<InstrumentFault[]>('/instruments/faults/open').then(r => r.data)

export const getInstrumentFaults = (): Promise<InstrumentFault[]> =>
  api.get<InstrumentFault[]>('/instruments/faults').then(r => r.data)

export const resolveInstrumentFault = (instId: number, faultId: number): Promise<InstrumentFault> =>
  api.put<InstrumentFault>(`/instruments/${instId}/fault/${faultId}/resolve`).then(r => r.data)

// Schedules
export const getTimeslots = (params?: Record<string, unknown>): Promise<TimeSlot[]> =>
  api.get<TimeSlot[]>('/schedules/timeslots', { params }).then(r => r.data);

export const generateSchedule = (projectIds?: number[]): Promise<{ status: string; message?: string }> =>
  api.post('/schedules/generate', { project_ids: projectIds }).then(r => r.data);

export const startTask = (slotId: number): Promise<{ status: string }> =>
  api.post(`/schedules/timeslots/${slotId}/start`).then(r => r.data);

export interface CompleteTaskRequest {
  release_instrument?: boolean
}

export interface CompleteTaskResponse {
  status: string
  message?: string
  moved_tasks?: number
  released_instrument?: boolean
}

export const completeTask = (
  slotId: number,
  data: CompleteTaskRequest = {},
): Promise<CompleteTaskResponse> =>
  api.post<CompleteTaskResponse>(`/schedules/timeslots/${slotId}/complete`, data).then(r => r.data);

export const interruptTask = (slotId: number): Promise<{ status: string }> =>
  api.post(`/schedules/timeslots/${slotId}/interrupt`).then(r => r.data);

export interface NightRunRequest {
  duration_hours: number
  earliest_start?: string
  latest_end?: string
  requires_operator: boolean
  remark?: string
}

export const recordNightRun = (slotId: number, data: NightRunRequest): Promise<TimeSlot> =>
  api.post<TimeSlot>(`/schedules/timeslots/${slotId}/night-run`, data).then(r => r.data)

export interface TaskDelayRequest {
  delay_hours: number
  reason: string
}

export interface TaskDelayResponse {
  status: string
  task_id: number
  slot_id: number
  delay_hours: number
  shifted_slots: number
  affected_tasks: number
  reason: string
}

export const reportTaskDelay = (slotId: number, data: TaskDelayRequest): Promise<TaskDelayResponse> =>
  api.post<TaskDelayResponse>(`/schedules/timeslots/${slotId}/delay`, data).then(r => r.data)

export const calculateInsertCost = (data: { project_id: number; task_ids: number[] }): Promise<InsertCost> =>
  api.post<InsertCost>('/schedules/insert-order', data).then(r => r.data);

export const confirmInsert = (data: { project_id: number; task_ids: number[] }): Promise<{ status: string }> =>
  api.post('/schedules/insert-order/confirm', data).then(r => r.data);

export const reschedule = (data: { trigger_type: string; strategy: string }): Promise<{ status: string }> =>
  api.post('/schedules/reschedule', data).then(r => r.data);

export const dailyRoll = (): Promise<{ status: string }> =>
  api.post('/schedules/daily-roll').then(r => r.data);



// Users
export interface User {
  id: number
  username: string
  display_name: string
  role: string
  email: string | null
  phone: string | null
  wecom_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserPayload {
  username: string
  display_name: string
  password?: string
  role: string
  email?: string | null
  phone?: string | null
  wecom_id?: string | null
  is_active: boolean
}

export const getUsers = (): Promise<User[]> =>
  api.get<User[]>('/users').then(r => r.data)

export const createUser = (data: UserPayload): Promise<User> =>
  api.post<User>('/users', data).then(r => r.data)

export const updateUser = (id: number, data: UserPayload): Promise<User> =>
  api.put<User>(`/users/${id}`, data).then(r => r.data)

export const deleteUser = (id: number): Promise<void> =>
  api.delete(`/users/${id}`)

export const logout = (): Promise<void> =>
  api.post('/users/logout').then(() => undefined)
// Schedule Rules
export type ScheduleRuleParamValue = string | number | boolean | number[] | null

export interface ScheduleRule {
  id: number
  category: string
  name: string
  code: string
  description: string | null
  params: Record<string, ScheduleRuleParamValue> | null
  is_enabled: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export const getScheduleRules = (): Promise<ScheduleRule[]> =>
  api.get<ScheduleRule[]>('/schedule-rules').then(r => r.data)

export const updateScheduleRule = (id: number, data: { params?: Record<string, ScheduleRuleParamValue>; is_enabled?: boolean; sort_order?: number }): Promise<ScheduleRule> =>
  api.put<ScheduleRule>(`/schedule-rules/${id}`, data).then(r => r.data)

export const toggleScheduleRule = (id: number): Promise<ScheduleRule> =>
  api.put<ScheduleRule>(`/schedule-rules/${id}/toggle`).then(r => r.data)

// My Tasks
export interface MyTask {
  slot_id: number; task_id: number; task_name: string | null; task_type: string | null
  project_id: number | null; project_name: string | null; project_code: string | null
  instrument_id: number; instrument_name: string | null; instrument_code: string | null
  plan_start: string | null; plan_end: string | null; actual_start: string | null; actual_end: string | null
  task_plan_start?: string | null; task_plan_end?: string | null
  status: string; tier: string; est_duration_hours: number | null
  delay_hours?: number | null; delay_reason?: string | null; delay_reported_at?: string | null
}

export const getMyTasks = (): Promise<MyTask[]> =>
  api.get<MyTask[]>('/schedules/my-tasks').then(r => r.data)

// Stats
export interface StatsRangeParams {
  start_date?: string
  end_date?: string
}

export const getDashboard = (params?: StatsRangeParams): Promise<DashboardData> =>
  api.get<DashboardData>('/stats/dashboard', { params }).then(r => r.data);

export const getUtilization = (params?: StatsRangeParams): Promise<UtilizationStats[]> =>
  api.get<UtilizationStats[]>('/stats/utilization', { params }).then(r => r.data);

// Task Types
export interface TaskTypeConfig {
  id: number
  name: string
  code: string
  resource_type: string
  description: string | null
  is_active: boolean
  sort_order: number
  predecessor_type_ids?: number[]
}

export const getTaskTypes = (): Promise<TaskTypeConfig[]> =>
  api.get<TaskTypeConfig[]>('/task-types').then(r => r.data)

export const createTaskType = (data: Partial<TaskTypeConfig>): Promise<TaskTypeConfig> =>
  api.post<TaskTypeConfig>('/task-types', data).then(r => r.data)

export const updateTaskType = (id: number, data: Partial<TaskTypeConfig>): Promise<TaskTypeConfig> =>
  api.put<TaskTypeConfig>('/task-types/' + id, data).then(r => r.data)

export const deleteTaskType = (id: number): Promise<void> =>
  api.delete('/task-types/' + id)

export interface AlertRule {
  id: number; name: string; rule_type: string; enabled: boolean;
  enable_site: boolean; enable_wecom: boolean;
  notify_roles: string | null; threshold_minutes: number; threshold_percent: number;
}
export const getAlertRules = (): Promise<AlertRule[]> =>
  api.get<AlertRule[]>('/alert-rules').then(r => r.data)
export const updateAlertRule = (id: number, data: Partial<AlertRule>): Promise<AlertRule> =>
  api.put<AlertRule>(`/alert-rules/${id}`, data).then(r => r.data)

export interface PushChannelConfig {
  id: number
  wecom_enabled: boolean
  wecom_corp_id: string | null
  wecom_agent_id: string | null
  wecom_secret: string | null
}

export const getPushConfig = (): Promise<PushChannelConfig> =>
  api.get<PushChannelConfig>('/alert-rules/push-config').then(r => r.data)

export const updatePushConfig = (data: Partial<PushChannelConfig>): Promise<PushChannelConfig> =>
  api.put<PushChannelConfig>('/alert-rules/push-config', data).then(r => r.data)

export interface NotificationRecord {
  id: number
  user_name: string
  n_type: string
  channel: string
  delivery_status: string
  error_message: string | null
  title: string | null
  content: string | null
  is_read: boolean
  is_confirmed: boolean | null
  created_at: string
}

export const getNotificationHistory = (limit = 200): Promise<NotificationRecord[]> =>
  api.get<NotificationRecord[]>('/notifications/history', { params: { limit } }).then(r => r.data)

export interface NotificationQuery {
  user_name: string
  channel?: string
  unread_only?: boolean
}

export const getNotifications = (params: NotificationQuery): Promise<NotificationRecord[]> =>
  api.get<NotificationRecord[]>('/notifications', { params }).then(r => r.data)

export const markNotificationRead = (id: number): Promise<{ status: string }> =>
  api.put<{ status: string }>(`/notifications/${id}/read`).then(r => r.data)

export const confirmNotification = (id: number): Promise<{ status: string }> =>
  api.post<{ status: string }>(`/notifications/${id}/confirm`).then(r => r.data)

export interface CalendarDay {
  id: number; date: string; is_working_day: boolean; holiday_name: string | null; day_type: string;
}
export const getCalendar = (year?: number, month?: number): Promise<CalendarDay[]> =>
  api.get<CalendarDay[]>('/calendar', { params: { year, month } }).then(r => r.data)
export const updateCalendarDay = (id: number, data: Partial<CalendarDay>): Promise<CalendarDay> =>
  api.put<CalendarDay>(`/calendar/${id}`, data).then(r => r.data)
export const upsertCalendarDate = (dt: string, data: Partial<CalendarDay>): Promise<CalendarDay> =>
  api.put<CalendarDay>(`/calendar/date/${dt}`, data).then(r => r.data)
export const batchFillCalendar = (year: number): Promise<{ detail: string }> =>
  api.post<{ detail: string }>('/calendar/batch-fill', { year }).then(r => r.data)
export const syncHolidays = (year: number): Promise<{ detail: string }> =>
  api.post<{ detail: string }>(`/calendar/sync/${year}`).then(r => r.data)

