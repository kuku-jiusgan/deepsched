import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'

import {
  isExceptionConfirmTask,
  isWorkspaceActiveTask,
  isWorkspacePendingTask,
  type WorkspaceTask,
} from './workspaceTask'


function task(overrides: Partial<WorkspaceTask> = {}): WorkspaceTask {
  return {
    task_id: 2,
    task_name: '方案撰写',
    task_type: 'QCFA_001',
    assignee_id: 3,
    assignee_name: '陈婷婷',
    project_id: 2,
    project_name: '塞来昔布原料药中基因毒杂质研究',
    project_code: 'XM2026195',
    execution_status: 'scheduled',
    est_duration_hours: 2,
    task_window: { start: '2026-07-17T21:00:00', end: '2026-07-20T09:30:00' },
    actual_window: { start: null, end: null },
    actionable_slot: {
      id: 57,
      instrument_id: null,
      instrument_name: null,
      instrument_code: null,
      plan_start: '2026-07-20T08:30:00',
      plan_end: '2026-07-20T09:30:00',
      actual_start: null,
      actual_end: null,
      tier: 'confirmed',
      status: 'scheduled',
    },
    segments: [],
    delay: { status: 'delayed', hours: null, reason: null, reported_at: null },
    ...overrides,
  }
}


describe('workspace task selectors', () => {
  const now = dayjs('2026-07-18T09:00:00')

  it('uses the full task start instead of the future actionable segment', () => {
    expect(isWorkspaceActiveTask(task(), now)).toBe(true)
    expect(isWorkspacePendingTask(task(), now)).toBe(false)
  })

  it('routes a persisted delayed task to exception confirmation', () => {
    expect(isExceptionConfirmTask(task(), now)).toBe(true)
  })

  it('keeps a task whose full start is in the future under pending', () => {
    const future = task({
      task_window: { start: '2026-07-20T08:30:00', end: '2026-07-20T09:30:00' },
      delay: { status: 'not_delayed', hours: null, reason: null, reported_at: null },
    })
    expect(isWorkspaceActiveTask(future, now)).toBe(false)
    expect(isWorkspacePendingTask(future, now)).toBe(true)
  })
})
