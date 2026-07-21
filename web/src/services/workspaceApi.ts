import { normalizeWorkspaceTask, type WorkspaceTask } from '@/domains/tasks/workspaceTask'
import http from './http'


export const getMyTasks = (): Promise<WorkspaceTask[]> =>
  http.get<unknown[]>('/schedules/my-tasks')
    .then(response => response.data.map(normalizeWorkspaceTask))
