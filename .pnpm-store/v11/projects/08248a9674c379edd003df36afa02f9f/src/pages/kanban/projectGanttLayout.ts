import dayjs from 'dayjs'
import type { TimeSlot } from '@/types'

export interface ProjectGanttSlot extends TimeSlot {
  mergedSlotIds: number[]
}

export interface ProjectLaneLayout {
  laneMap: Record<number, Record<number, number>>
  laneCounts: Record<number, number>
}

export function buildProjectDisplaySlots(sourceSlots: TimeSlot[]): ProjectGanttSlot[] {
  const displaySlots = sourceSlots.flatMap(slot => {
    if (slot.status !== 'completed') return [slot]
    if (!slot.actual_start || !slot.actual_end) return []
    return [{ ...slot, plan_start: slot.actual_start, plan_end: slot.actual_end }]
  })
  return mergeContinuousSlots(displaySlots)
}

export function buildProjectLaneLayout(
  projectIds: number[],
  displaySlots: ProjectGanttSlot[],
): ProjectLaneLayout {
  const laneMap: Record<number, Record<number, number>> = {}
  const laneCounts: Record<number, number> = {}
  for (const projectId of projectIds) {
    const projectSlots = displaySlots
      .filter(slot => slot.project_id === projectId)
      .sort((left, right) => dayjs(left.plan_start).valueOf() - dayjs(right.plan_start).valueOf())
    const laneEnds: dayjs.Dayjs[] = []
    const assignments: Record<number, number> = {}
    for (const slot of projectSlots) {
      const start = dayjs(slot.plan_start)
      const availableLane = laneEnds.findIndex(end => !start.isBefore(end))
      const lane = availableLane === -1 ? laneEnds.length : availableLane
      laneEnds[lane] = dayjs(slot.plan_end)
      assignments[slot.id] = lane
    }
    laneMap[projectId] = assignments
    laneCounts[projectId] = Math.max(1, laneEnds.length)
  }
  return { laneMap, laneCounts }
}

function mergeContinuousSlots(sourceSlots: TimeSlot[]): ProjectGanttSlot[] {
  const sortedSlots = [...sourceSlots].sort((left, right) => {
    const projectDiff = (left.project_id || 0) - (right.project_id || 0)
    if (projectDiff !== 0) return projectDiff
    const startDiff = dayjs(left.plan_start).valueOf() - dayjs(right.plan_start).valueOf()
    return startDiff || left.id - right.id
  })

  const mergedSlots: ProjectGanttSlot[] = []
  for (const slot of sortedSlots) {
    const previousSlot = mergedSlots[mergedSlots.length - 1]
    if (previousSlot && canMergeSlots(previousSlot, slot)) {
      previousSlot.plan_end = slot.plan_end
      previousSlot.actual_end = slot.actual_end || previousSlot.actual_end
      previousSlot.mergedSlotIds.push(slot.id)
      if (hasDelayData(slot)) {
        previousSlot.delay_hours = slot.delay_hours
        previousSlot.delay_reason = slot.delay_reason
        previousSlot.delay_reported_at = slot.delay_reported_at
      }
      continue
    }
    mergedSlots.push({ ...slot, mergedSlotIds: [slot.id] })
  }
  return mergedSlots
}

function canMergeSlots(current: ProjectGanttSlot, next: TimeSlot) {
  return current.project_id === next.project_id
    && current.task_id === next.task_id
    && current.instrument_id === next.instrument_id
    && current.status === next.status
    && current.tier === next.tier
    && dayjs(current.plan_end).isSame(dayjs(next.plan_start))
}

function hasDelayData(slot: TimeSlot) {
  return Boolean(slot.delay_reason) || Number(slot.delay_hours || 0) > 0
}
