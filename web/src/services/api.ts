import axios from 'axios';
import type {
  Project, Instrument, TimeSlot, DashboardData, UtilizationStats,
  DAGData, InsertCost, Task, Milestone, CapabilityReq,
} from '../types';

const api = axios.create({ baseURL: '/api/v1' });

// Shared types

interface GenerateResult {
  status: string;
  message?: string;
  timeslots_created?: number;
}

interface ActionResult {
  status: string;
}

interface DailyRollResult {
  status: string;
  rolled_at: string;
}

interface TimeslotParams {
  start_date?: string;
  end_date?: string;
  instrument_id?: number;
  project_id?: number;
  tier?: string;
}

interface InsertOrderPayload {
  project_id: number;
  task_ids: number[];
}

interface ReschedulePayload {
  trigger_type: string;
  strategy: string;
}

// Projects

export const getProjects = (): Promise<Project[]> =>
  api.get<Project[]>('/projects').then(r => r.data);

export const getProject = (id: number): Promise<Project> =>
  api.get<Project>(`/projects/${id}`).then(r => r.data);

export const createProject = (data: Partial<Project>): Promise<Project> =>
  api.post<Project>('/projects', data).then(r => r.data);

export const updateProject = (id: number, data: Partial<Project>): Promise<Project> =>
  api.put<Project>(`/projects/${id}`, data).then(r => r.data);

export const getProjectDAG = (id: number): Promise<DAGData> =>
  api.get<DAGData>(`/projects/${id}/dag`).then(r => r.data);

export const updateTask = (taskId: number, data: {
  name: string;
  task_type: string;
  requires_instrument: boolean;
  est_duration_hours: number;
  switchover_hours: number;
  predecessor_ids: number[];
  capability_requirements: CapabilityReq[];
}): Promise<Task> =>
  api.put<Task>(`/projects/tasks/${taskId}`, data).then(r => r.data);

export const addTask = (projId: number, data: {
  name: string;
  task_type: string;
  requires_instrument: boolean;
  est_duration_hours: number;
  switchover_hours: number;
  predecessor_ids: number[];
  capability_requirements: CapabilityReq[];
}): Promise<Task> =>
  api.post<Task>(`/projects/${projId}/tasks`, data).then(r => r.data);

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

export const getTimeslots = (params?: TimeslotParams): Promise<TimeSlot[]> =>
  api.get<TimeSlot[]>('/schedules/timeslots', { params }).then(r => r.data);

export const updateTimeslot = (id: number, data: Partial<TimeSlot>): Promise<TimeSlot> =>
  api.put<TimeSlot>(`/schedules/timeslots/${id}`, data).then(r => r.data);

export const generateSchedule = (projectIds?: number[]): Promise<GenerateResult> =>
  api.post<GenerateResult>('/schedules/generate', { project_ids: projectIds }).then(r => r.data);

export const startTask = (slotId: number): Promise<ActionResult> =>
  api.post<ActionResult>(`/schedules/timeslots/${slotId}/start`).then(r => r.data);

export const completeTask = (slotId: number): Promise<ActionResult> =>
  api.post<ActionResult>(`/schedules/timeslots/${slotId}/complete`).then(r => r.data);

export const interruptTask = (slotId: number): Promise<ActionResult> =>
  api.post<ActionResult>(`/schedules/timeslots/${slotId}/interrupt`).then(r => r.data);

export const calculateInsertCost = (data: InsertOrderPayload): Promise<InsertCost> =>
  api.post<InsertCost>('/schedules/insert-order', data).then(r => r.data);

export const confirmInsert = (data: InsertOrderPayload): Promise<ActionResult> =>
  api.post<ActionResult>('/schedules/insert-order/confirm', data).then(r => r.data);

export const reschedule = (data: ReschedulePayload): Promise<GenerateResult> =>
  api.post<GenerateResult>('/schedules/reschedule', data).then(r => r.data);

export const dailyRoll = (): Promise<DailyRollResult> =>
  api.post<DailyRollResult>('/schedules/daily-roll').then(r => r.data);

// Stats

export const getDashboard = (): Promise<DashboardData> =>
  api.get<DashboardData>('/stats/dashboard').then(r => r.data);

export const getUtilization = (): Promise<UtilizationStats[]> =>
  api.get<UtilizationStats[]>('/stats/utilization').then(r => r.data);

// Notifications

export const getNotifications = (): Promise<unknown[]> =>
  api.get<unknown[]>('/notifications').then(r => r.data);
