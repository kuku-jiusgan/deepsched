import axios from 'axios';
import type { Project, Instrument, TimeSlot, DashboardData, UtilizationStats, DAGData, InsertCost } from '../types';

const api = axios.create({ baseURL: '/api/v1' });

// Projects
export const getProjects = () => api.get<Project[]>('/projects').then(r => r.data);
export const getProject = (id: number) => api.get<Project>(`/projects/${id}`).then(r => r.data);
export const createProject = (data: Partial<Project>) => api.post<Project>('/projects', data).then(r => r.data);
export const getProjectDAG = (id: number) => api.get<DAGData>(`/projects/${id}/dag`).then(r => r.data);
export const addTask = (projId: number, data: any) => api.post(`/projects/${projId}/tasks`, data).then(r => r.data);

// Instruments
export const getInstruments = () => api.get<Instrument[]>('/instruments').then(r => r.data);
export const createInstrument = (data: Partial<Instrument>) => api.post<Instrument>('/instruments', data).then(r => r.data);
export const updateInstrument = (id: number, data: Partial<Instrument>) => api.put<Instrument>(`/instruments/${id}`, data).then(r => r.data);

// Schedules
export const getTimeslots = (params?: any) => api.get<TimeSlot[]>('/schedules/timeslots', { params }).then(r => r.data);
export const updateTimeslot = (id: number, data: any) => api.put(`/schedules/timeslots/${id}`, data).then(r => r.data);
export const generateSchedule = (projectIds?: number[]) => api.post('/schedules/generate', { project_ids: projectIds }).then(r => r.data);
export const startTask = (slotId: number) => api.post(`/schedules/timeslots/${slotId}/start`).then(r => r.data);
export const completeTask = (slotId: number) => api.post(`/schedules/timeslots/${slotId}/complete`).then(r => r.data);
export const interruptTask = (slotId: number) => api.post(`/schedules/timeslots/${slotId}/interrupt`).then(r => r.data);
export const calculateInsertCost = (data: any) => api.post<InsertCost>('/schedules/insert-order', data).then(r => r.data);
export const confirmInsert = (data: any) => api.post('/schedules/insert-order/confirm', data).then(r => r.data);
export const reschedule = (data: any) => api.post('/schedules/reschedule', data).then(r => r.data);
export const dailyRoll = () => api.post('/schedules/daily-roll').then(r => r.data);

// Stats
export const getDashboard = () => api.get<DashboardData>('/stats/dashboard').then(r => r.data);
export const getUtilization = () => api.get<UtilizationStats[]>('/stats/utilization').then(r => r.data);

// Notifications
export const getNotifications = () => api.get('/notifications').then(r => r.data);