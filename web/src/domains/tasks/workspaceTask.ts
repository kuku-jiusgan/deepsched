import dayjs, { type Dayjs } from 'dayjs'

export interface TaskTimeWindow {
  start: string | null
  end: string | null
}

export interface WorkspaceSegment {
  id: number
  instrument_id: number | null
  instrument_name: string | null
  instrument_code: string | null
  plan_start: string
  plan_end: string
  actual_start: string | null
  actual_end: string | null
  tier: string
  status: string
}

export interface WorkspaceDelay {
  status: 'delayed' | 'not_delayed'
  hours: number | null
  reason: string | null
  reported_at: string | null
}

export interface WorkspaceTask {
  task_id: number
  task_name: string | null
  task_type: string | null
  assignee_id: number | null
  assignee_name: string | null
  project_id: number | null
  project_name: string | null
  project_code: string | null
  execution_status: string
  est_duration_hours: number | null
  task_window: TaskTimeWindow
  actual_window: TaskTimeWindow
  actionable_slot: WorkspaceSegment | null
  segments: WorkspaceSegment[]
  delay: WorkspaceDelay
}

export function isTaskClosed(task: WorkspaceTask) {
  return ['done', 'completed'].includes(task.execution_status)
}

export function isTaskDue(task: WorkspaceTask, now: Dayjs = dayjs()) {
  if (!task.task_window.start) return false
  return !dayjs(task.task_window.start).isAfter(now.endOf('day'))
}

export function isDuePendingTask(task: WorkspaceTask, now: Dayjs = dayjs()) {
  return ['pending', 'scheduled'].includes(task.execution_status) && isTaskDue(task, now)
}

export function isWorkspaceActiveTask(task: WorkspaceTask, now: Dayjs = dayjs()) {
  return ['running', 'blocked', 'interrupted'].includes(task.execution_status) || isDuePendingTask(task, now)
}

export function isWorkspacePendingTask(task: WorkspaceTask, now: Dayjs = dayjs()) {
  return ['pending', 'scheduled'].includes(task.execution_status) && !isDuePendingTask(task, now)
}

export function isExceptionConfirmTask(task: WorkspaceTask, now: Dayjs = dayjs()) {
  const isProblemStatus = ['blocked', 'interrupted'].includes(task.execution_status)
  const isOverdue = Boolean(task.task_window.end)
    && dayjs(task.task_window.end).isBefore(now)
    && !isTaskClosed(task)
  return task.delay.status === 'delayed'
    || isProblemStatus
    || isOverdue
    || Boolean(task.delay.reason)
    || Boolean(task.delay.hours)
}

export function actionableSlotId(task: WorkspaceTask) {
  return task.actionable_slot?.id ?? null
}
