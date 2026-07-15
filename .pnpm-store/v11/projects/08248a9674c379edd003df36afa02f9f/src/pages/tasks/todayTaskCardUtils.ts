import dayjs from 'dayjs'
import type { MyTask } from '@/services/api'

interface StoredUser {
  display_name?: string
  username?: string
}

export function normalizeWorkdayEndTime(value: unknown) {
  if (typeof value === 'string' && /^\d{2}:\d{2}$/.test(value)) return value
  if (typeof value === 'number' && Number.isFinite(value)) {
    const totalMinutes = Math.round(value * 60)
    const hours = Math.floor(totalMinutes / 60).toString().padStart(2, '0')
    const minutes = (totalMinutes % 60).toString().padStart(2, '0')
    return `${hours}:${minutes}`
  }
  return null
}

export function formatHours(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function currentUserName() {
  const rawUser = localStorage.getItem('user')
  if (!rawUser) return '当前用户'
  try {
    const user = JSON.parse(rawUser) as StoredUser
    return user.display_name || user.username || '当前用户'
  } catch {
    return '当前用户'
  }
}

export function isTodayTask(task: MyTask) {
  if (isTaskClosed(task)) return false
  if (task.status === 'running') return true
  if (!task.plan_start) return false
  return dayjs(task.plan_start).isBefore(dayjs().endOf('day')) || dayjs(task.plan_start).isSame(dayjs().endOf('day'))
}

export function isTaskClosed(task: MyTask) {
  return ['done', 'completed'].includes(task.status)
}

export function canStartTask(task: MyTask) {
  return ['pending', 'scheduled'].includes(task.status) && Boolean(task.slot_id)
}

export function canCompleteTask(task: MyTask) {
  return task.status === 'running' && Boolean(task.slot_id)
}

export function isExceptionConfirmTask(task: MyTask) {
  const isProblemStatus = ['blocked', 'interrupted'].includes(task.status)
  const plannedEnd = task.task_plan_end || task.plan_end
  const isOverdue = Boolean(plannedEnd) && dayjs(plannedEnd).isBefore(dayjs()) && !isTaskClosed(task)
  const hasDelayReport = Boolean(task.delay_reason) || Boolean(task.delay_hours)
  return isProblemStatus || isOverdue || hasDelayReport
}

export function formatTaskTime(value: string | dayjs.Dayjs | null, fallback: string) {
  return value ? dayjs(value).format('HH:mm') : fallback
}

function formatTaskDateTime(value: string | dayjs.Dayjs | null, fallback: string) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : fallback
}

export function nightRunEndTime(task: MyTask) {
  if (!task.plan_end) return null
  const planEnd = dayjs(task.plan_end)
  if (task.status === 'running' && task.actual_start) {
    const actualStart = dayjs(task.actual_start)
    return actualStart.hour(planEnd.hour()).minute(planEnd.minute()).second(0).millisecond(0)
  }
  return planEnd
}

export function parseNightClock(baseTime: dayjs.Dayjs, value: string) {
  if (!value) return null
  const cleanValue = value.trim()
  const isNextDay = cleanValue.startsWith('次日')
  const match = cleanValue.replace('次日', '').trim().match(/^(\d{1,2}):(\d{2})$/)
  if (!match) return null
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (hour > 23 || minute > 59) return null
  let parsedTime = baseTime.hour(hour).minute(minute).second(0).millisecond(0)
  if (isNextDay || parsedTime.isBefore(baseTime)) parsedTime = parsedTime.add(1, 'day')
  return parsedTime
}

export function maxNightRunHours(earliestStart: string, latestEnd: string) {
  const start = parseNightClock(dayjs(), earliestStart)
  if (!start) return 0
  const end = parseNightClock(start, latestEnd)
  if (!end || !end.isAfter(start)) return 0
  return Math.floor(end.diff(start, 'minute') / 30) * 0.5
}

export function isHalfHourDuration(value: unknown) {
  return typeof value === 'number' && Number.isInteger(value * 2)
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待处理', scheduled: '待执行', running: '运行中', completed: '已完成',
    done: '已完成', blocked: '已延期', interrupted: '已中断',
  }
  return labels[status] || status
}

export function scheduleText(task: MyTask) {
  const startText = formatTaskDateTime(task.task_plan_start || task.plan_start, '---- -- -- --:--')
  const endText = formatTaskDateTime(task.task_plan_end || task.plan_end, '---- -- -- --:--')
  return `${startText}–${endText}`
}

export function actualText(task: MyTask) {
  return `${formatTaskDateTime(task.actual_start, '---- -- -- --:--')}–${formatTaskDateTime(task.actual_end, '---- -- -- --:--')}`
}

export function formatProjectText(task: MyTask) {
  const parts = [task.project_code, task.project_name].filter(Boolean)
  return parts.length ? parts.join(' · ') : '未关联项目'
}

export function formatInstrumentText(task: MyTask) {
  if (task.instrument_code && task.instrument_name) return `${task.instrument_code} · ${task.instrument_name}`
  return task.instrument_code || task.instrument_name || '未指定仪器'
}

export function getDelayText(task: MyTask) {
  if (!task.delay_reason && !task.delay_hours) return ''
  const hoursText = task.delay_hours ? `${task.delay_hours}h` : ''
  return [hoursText, task.delay_reason || '未填写原因'].filter(Boolean).join(' · ')
}
