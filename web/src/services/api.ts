import axios from 'axios';
import type {
  Project, Instrument, TimeSlot, DashboardData, UtilizationStats,
  DAGData, InsertCost, Task, CapabilityReq,
} from '@/types';


const api = axios.create({ baseURL: '/api/v1' });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.params = { ...config.params, token }
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
  predecessor_ids: number[]; capability_requirements: CapabilityReq[];
}): Promise<Task> =>
  api.post<Task>(`/projects/${projId}/tasks`, data).then(r => r.data);


export const deleteTask = (id: number): Promise<void> =>
  api.delete(`/projects/tasks/${id}`)

export const updateTask = (taskId: number, data: {
  name: string; task_type: string; requires_instrument: boolean;
  est_duration_hours: number; switchover_hours: number;
  predecessor_ids: number[]; capability_requirements: CapabilityReq[];
}): Promise<Task> =>
  api.put<Task>(`/projects/tasks/${taskId}`, data).then(r => r.data);

// Instruments
export const getInstruments = (): Promise<Instrument[]> =>
  api.get<Instrument[]>('/instruments').then(r => r.data);

export const createInstrument = (data: Partial<Instrument>): Promise<Instrument> =>
  api.post<Instrument>('/instruments', data).then(r => r.data);

export const updateInstrument = (id: number, data: Partial<Instrument>): Promise<Instrument> =>
  api.put<Instrument>(`/instruments/${id}`, data).then(r => r.data);

export const deleteInstrument = (id: number): Promise<void> =>
  api.delete(`/instruments/${id}`);

// Schedules
export const getTimeslots = (params?: Record<string, unknown>): Promise<TimeSlot[]> =>
  api.get<TimeSlot[]>('/schedules/timeslots', { params }).then(r => r.data);

export const generateSchedule = (projectIds?: number[]): Promise<{ status: string; message?: string }> =>
  api.post('/schedules/generate', { project_ids: projectIds }).then(r => r.data);

export const startTask = (slotId: number): Promise<{ status: string }> =>
  api.post(`/schedules/timeslots/${slotId}/start`).then(r => r.data);

export const completeTask = (slotId: number): Promise<{ status: string }> =>
  api.post(`/schedules/timeslots/${slotId}/complete`).then(r => r.data);

export const interruptTask = (slotId: number): Promise<{ status: string }> =>
  api.post(`/schedules/timeslots/${slotId}/interrupt`).then(r => r.data);

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
  is_active: boolean
  created_at: string
  updated_at: string
}

export const getUsers = (): Promise<User[]> =>
  api.get<User[]>('/users').then(r => r.data)

export const createUser = (data: Partial<User>): Promise<User> =>
  api.post<User>('/users', data).then(r => r.data)

export const updateUser = (id: number, data: Partial<User>): Promise<User> =>
  api.put<User>(`/users/${id}`, data).then(r => r.data)

export const deleteUser = (id: number): Promise<void> =>
  api.delete(`/users/${id}`)
// Schedule Rules
export interface ScheduleRule {
  id: number
  category: string
  name: string
  code: string
  description: string | null
  params: Record<string, any> | null
  is_enabled: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export const getScheduleRules = (): Promise<ScheduleRule[]> =>
  api.get<ScheduleRule[]>('/schedule-rules').then(r => r.data)

export const updateScheduleRule = (id: number, data: { params?: Record<string, any>; is_enabled?: boolean; sort_order?: number }): Promise<ScheduleRule> =>
  api.put<ScheduleRule>(`/schedule-rules/${id}`, data).then(r => r.data)

export const toggleScheduleRule = (id: number): Promise<ScheduleRule> =>
  api.put<ScheduleRule>(`/schedule-rules/${id}/toggle`).then(r => r.data)

// My Tasks
export interface MyTask {
  slot_id: number; task_id: number; task_name: string | null; task_type: string | null
  project_id: number | null; project_name: string | null; project_code: string | null
  instrument_id: number; instrument_name: string | null; instrument_code: string | null
  plan_start: string | null; plan_end: string | null; actual_start: string | null
  status: string; tier: string; est_duration_hours: number | null
}

export const getMyTasks = (): Promise<MyTask[]> =>
  api.get<MyTask[]>('/schedules/my-tasks').then(r => r.data)

// Stats
export const getDashboard = (): Promise<DashboardData> =>
  api.get<DashboardData>('/stats/dashboard').then(r => r.data);

export const getUtilization = (): Promise<UtilizationStats[]> =>
  api.get<UtilizationStats[]>('/stats/utilization').then(r => r.data);

// Task Types
export interface TaskTypeConfig {
  id: number
  name: string
  code: string
  resource_type: string
  description: string | null
  is_active: boolean
  sort_order: number
}

export const getTaskTypes = (): Promise<TaskTypeConfig[]> =>
  api.get<TaskTypeConfig[]>('/task-types').then(r => r.data)

export const createTaskType = (data: Partial<TaskTypeConfig>): Promise<TaskTypeConfig> =>
  api.post<TaskTypeConfig>('/task-types', data).then(r => r.data)

export const updateTaskType = (id: number, data: Partial<TaskTypeConfig>): Promise<TaskTypeConfig> =>
  api.put<TaskTypeConfig>('/task-types/' + id, data).then(r => r.data)

export const deleteTaskType = (id: number): Promise<void> =>
  api.delete('/task-types/' + id)

