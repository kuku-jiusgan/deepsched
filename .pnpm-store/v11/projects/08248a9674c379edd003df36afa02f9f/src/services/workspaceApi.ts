import type { WorkspaceTask } from '@/domains/tasks/workspaceTask'
import http from './http'


export const getMyTasks = (): Promise<WorkspaceTask[]> =>
  http.get<WorkspaceTask[]>('/schedules/my-tasks').then(response => response.data)
