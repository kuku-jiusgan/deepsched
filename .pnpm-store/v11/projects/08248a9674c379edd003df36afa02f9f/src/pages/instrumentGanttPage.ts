
import { ref, computed, nextTick } from 'vue'
import type { CSSProperties, Component } from 'vue'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined, FullscreenOutlined, FullscreenExitOutlined, ExperimentOutlined, EditOutlined, CheckSquareOutlined, DotChartOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getInstruments, getTimeslots, getTaskTypes, type TaskTypeConfig } from '@/services/api'
import type { Instrument, TimeSlot } from '@/types'
import dayjs from 'dayjs'
import { centerGanttTimelineOnCurrentTime } from './kanban/ganttTimelineScroll'
import { useGanttAutoScroll } from './kanban/useGanttAutoScroll'

const LEFT_WIDTH = 250
const HEADER_HEIGHT = 50
const WEEK_QUARTER_ROW_HEIGHT = 42
const WEEK_SEGMENT_COUNT = 3
const WEEK_SEGMENT_HOURS = 8
const WEEK_SEGMENT_SECONDS = WEEK_SEGMENT_HOURS * 60 * 60
const ENTITY_ROW_HEIGHT = 72
const MIN_COL_WIDTH = 72
const WEEK_BAR_TINY_WIDTH = 32
const WEEK_BAR_ICON_WIDTH = 52
const WEEK_BAR_FULL_WIDTH = 74
const DELAY_PROBLEM_STATUSES = new Set(['blocked', 'interrupted'])

type SlotStatusKey = 'scheduled' | 'running' | 'completed' | 'blocked'
type InstrumentStatusKey = 'idle' | 'running' | 'maintenance' | 'fault' | 'disabled' | 'unknown'

interface StatusMeta {
  key: SlotStatusKey
  label: string
}

interface InstrumentStatusMeta {
  key: InstrumentStatusKey
  label: string
}

interface WeekBarSegment {
  quarter: number
  width: number
  visibleSeconds: number
}

interface WeekBarDisplay {
  showIcon: boolean
  showLabel: boolean
  projectText: string
  taskText: string
}

interface GanttSlot extends TimeSlot {
  mergedSlotIds?: number[]
}

const slotStatusMetaMap: Record<string, StatusMeta> = {
  scheduled: { key: 'scheduled', label: '待执行' },
  pending: { key: 'scheduled', label: '待执行' },
  running: { key: 'running', label: '运行中' },
  completed: { key: 'completed', label: '已完成' },
  blocked: { key: 'blocked', label: '已延期' },
  interrupted: { key: 'blocked', label: '已中断' },
}

const instrumentStatusMetaMap: Record<string, InstrumentStatusMeta> = {
  idle: { key: 'idle', label: '空闲' },
  running: { key: 'running', label: '运行' },
  maintenance: { key: 'maintenance', label: '维护' },
  fault: { key: 'fault', label: '故障' },
  disabled: { key: 'disabled', label: '停用' },
}

const loading = ref(true)
const instruments = ref<Instrument[]>([])
const slots = ref<TimeSlot[]>([])
const viewMode = ref<'day' | 'week' | 'month'>('week')
const cursorDate = ref(dayjs().startOf('week'))
const isFullscreen = ref(false)
const hoveredSlot = ref<GanttSlot | null>(null)
const tooltipX = ref(0)
const tooltipY = ref(0)
const tooltipStyle = computed(() => ({ left: tooltipX.value + 'px', top: tooltipY.value + 'px' }))
const containerRef = ref<HTMLElement | null>(null)
const {
  autoScrollEnabled,
  hasVerticalOverflow,
  getMaxVerticalScroll,
  scheduleAutoScrollStart,
  toggleFullscreen,
} = useGanttAutoScroll({
  containerRef,
  isFullscreen,
  recalculate: recalc,
  refresh: fetchData,
})
const leftRef = ref<HTMLElement | null>(null)
const rightRef = ref<HTMLElement | null>(null)
const colWidth = ref(140)
const rowHeight = ref(WEEK_QUARTER_ROW_HEIGHT)
const taskTypeMap = ref<Record<string, string>>({})
const laneMap = ref<Record<number, Record<number, number>>>({})
const laneCounts = ref<Record<number, number>>({})

const flatRows = computed(() => {
  const rows: { inst: Instrument; quarter: number; isSubrow: boolean; isLast: boolean }[] = []
  for (const inst of instruments.value) {
    const qCount = viewMode.value === 'week' ? WEEK_SEGMENT_COUNT : 1
    for (let q = 0; q < qCount; q++) {
      rows.push({ inst, quarter: q, isSubrow: viewMode.value === 'week' && q > 0, isLast: q === qCount - 1 })
    }
  }
  return rows
})

const totalWidth = computed(() => colWidth.value * timeColumns.value.length)

const periodLabel = computed(() => {
  const start = cursorDate.value
  if (viewMode.value === 'day') return start.format('YYYY年MM月DD日')
  if (viewMode.value === 'week') {
    const end = start.add(6, 'day')
    return `${start.format('MM/DD')} - ${end.format('MM/DD')}`
  }
  return start.format('YYYY年MM月')
})

interface TimeCol {
  key: string; label: string; subLabel: string; isWeekend: boolean; isToday: boolean; isCurrent: boolean
  start: dayjs.Dayjs; end: dayjs.Dayjs
}

const timeColumns = computed<TimeCol[]>(() => {
  const cols: TimeCol[] = []
  const now = dayjs()
  const today = now.format('YYYY-MM-DD')
  if (viewMode.value === 'day') {
    for (let h = 0; h < 24; h++) {
      const d = cursorDate.value.hour(h)
      cols.push({
        key: 'h' + h, label: String(h).padStart(2, '0') + ':00', subLabel: '', isWeekend: false,
        isToday: d.format('YYYY-MM-DD') === today,
        isCurrent: d.format('YYYY-MM-DD') === today && h === now.hour(),
        start: d,
        end: d.add(1, 'hour')
      })
    }
  } else if (viewMode.value === 'week') {
    for (let i = 0; i < 7; i++) {
      const d = cursorDate.value.add(i, 'day')
      const dow = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.day()]
      cols.push({
        key: 'd' + i, label: dow, subLabel: d.format('MM/DD'),
        isWeekend: d.day() === 0 || d.day() === 6,
        isToday: d.format('YYYY-MM-DD') === today,
        isCurrent: d.format('YYYY-MM-DD') === today,
        start: d.startOf('day'),
        end: d.endOf('day')
      })
    }
  } else {
    const daysInMonth = cursorDate.value.daysInMonth()
    for (let i = 0; i < daysInMonth; i++) {
      const d = cursorDate.value.date(i + 1)
      const dow = ['日', '一', '二', '三', '四', '五', '六'][d.day()]
      cols.push({
        key: 'd' + i, label: (i + 1) + '日', subLabel: '周' + dow,
        isWeekend: d.day() === 0 || d.day() === 6,
        isToday: d.format('YYYY-MM-DD') === today,
        isCurrent: d.format('YYYY-MM-DD') === today,
        start: d.startOf('day'),
        end: d.endOf('day')
      })
    }
  }
  return cols
})

const displaySlots = computed<GanttSlot[]>(() => mergeContinuousSlots(toDisplaySlots(slots.value)))

function computeLanes() {
  const map: Record<number, Record<number, number>> = {}
  const counts: Record<number, number> = {}
  for (const inst of instruments.value) {
    const instSlots = displaySlots.value.filter(s => s.instrument_id === inst.id).sort((a, b) => dayjs(a.plan_start).valueOf() - dayjs(b.plan_start).valueOf())
    const lanes: { end: dayjs.Dayjs }[] = []
    const assign: Record<number, number> = {}
    for (const slot of instSlots) {
      const start = dayjs(slot.plan_start)
      let placed = false
      for (let i = 0; i < lanes.length; i++) {
        if (start.isAfter(lanes[i].end) || start.isSame(lanes[i].end)) {
          lanes[i].end = dayjs(slot.plan_end)
          assign[slot.id] = i
          placed = true
          break
        }
      }
      if (!placed) {
        assign[slot.id] = lanes.length
        lanes.push({ end: dayjs(slot.plan_end) })
      }
    }
    map[inst.id] = assign
    counts[inst.id] = Math.max(1, lanes.length)
  }
  laneMap.value = map
  laneCounts.value = counts
}

function getLeftRowStyle(row: { isSubrow: boolean }): CSSProperties {
  if (viewMode.value === 'week' && !row.isSubrow) {
    return { height: rowHeight.value * WEEK_SEGMENT_COUNT + 'px' }
  }
  if (viewMode.value === 'week' && row.isSubrow) {
    return { height: '0', overflow: 'hidden', padding: '0', border: 'none' }
  }
  return { height: Math.max(12, rowHeight.value) + 'px' }
}

function getSegmentStartHour(quarter: number) {
  return quarter * WEEK_SEGMENT_HOURS
}

function getSegmentEndHour(quarter: number) {
  return Math.min(24, getSegmentStartHour(quarter) + WEEK_SEGMENT_HOURS)
}

function getSegmentLabel(quarter: number) {
  const start = String(getSegmentStartHour(quarter)).padStart(2, '0')
  const end = String(getSegmentEndHour(quarter)).padStart(2, '0')
  return `${start}-${end}`
}

function getBarClasses(slot: GanttSlot, quarter?: number) {
  const statusMeta = getSlotStatusMeta(slot.status)
  return [
    'status-' + statusMeta.key,
    {
      'is-compact': isCompactBar(slot, quarter),
      'has-delay': hasDelay(slot),
    },
  ]
}

function getSlotsForQuarter(instId: number, quarter: number) {
  if (viewMode.value !== 'week') return getSlotsForInstrument(instId)
  const cols = timeColumns.value
  return getSlotsForInstrument(instId).filter(s => {
    const start = dayjs(s.plan_start)
    const end = dayjs(s.plan_end)
    for (const col of cols) {
      const dayStart = col.start
      const qStart = dayStart.hour(getSegmentStartHour(quarter))
      const qEnd = dayStart.hour(getSegmentEndHour(quarter))
      if (end.isAfter(qStart) && start.isBefore(qEnd)) return true
    }
    return false
  })
}

function getSlotsForInstrument(instId: number) {
  return displaySlots.value.filter(s => s.instrument_id === instId)
}

function getBarStyle(slot: GanttSlot, quarter?: number) {
  const start = dayjs(slot.plan_start)
  const end = dayjs(slot.plan_end)
  const cols = timeColumns.value
  const cw = colWidth.value

  let startCol = -1, endCol = -1
  for (let i = 0; i < cols.length; i++) {
    if (startCol === -1 && end.isAfter(cols[i].start) && start.isBefore(cols[i].end)) startCol = i
    if (end.isAfter(cols[i].start) && start.isBefore(cols[i].end)) endCol = i
  }
  if (startCol === -1 || endCol === -1) return { display: 'none' }

  const colStart = cols[startCol].start
  const colDuration = cols[startCol].end.diff(colStart, 'second', true)
  const startOffset = Math.max(0, start.diff(colStart, 'second', true)) / Math.max(1, colDuration)

  const endColStart = cols[endCol].start
  const endColDuration = cols[endCol].end.diff(endColStart, 'second', true)
  const endOffset = Math.min(1, end.diff(endColStart, 'second', true) / Math.max(1, endColDuration))

  const left = (startCol + startOffset) * cw
  const right = (endCol + endOffset) * cw

  // In week view, position within the current 8-hour segment row.
  if (viewMode.value === 'week' && quarter !== undefined) {
    let barStartCol = -1, barEndCol = -1
    for (let i = 0; i < cols.length; i++) {
      const dayStart = cols[i].start
      const qStart = dayStart.hour(getSegmentStartHour(quarter))
      const qEnd = dayStart.hour(getSegmentEndHour(quarter))
      if (end.isAfter(qStart) && start.isBefore(qEnd)) {
        if (barStartCol === -1) barStartCol = i
        barEndCol = i
      }
    }
    if (barStartCol === -1) return { display: 'none' }
    const firstDayStart = cols[barStartCol].start
    const firstQStart = firstDayStart.hour(getSegmentStartHour(quarter))
    const firstQEnd = firstDayStart.hour(getSegmentEndHour(quarter))
    const clampedStart = start.isBefore(firstQStart) ? firstQStart : start
    const firstOffset = clampedStart.diff(firstQStart, 'second', true) / WEEK_SEGMENT_SECONDS
    const lastDayStart = cols[barEndCol].start
    const lastQStart = lastDayStart.hour(getSegmentStartHour(quarter))
    const lastQEnd = lastDayStart.hour(getSegmentEndHour(quarter))
    const clampedEnd = end.isAfter(lastQEnd) ? lastQEnd : end
    const lastOffset = clampedEnd.diff(lastQStart, 'second', true) / WEEK_SEGMENT_SECONDS
    const barLeft = (barStartCol + firstOffset) * cw
    const barRight = (barEndCol + lastOffset) * cw
    return {
      left: barLeft + 'px',
      width: Math.max(3, barRight - barLeft) + 'px',
      top: '4px',
      height: Math.max(28, rowHeight.value - 8) + 'px',
    }
  }

  const lane = (laneMap.value[slot.instrument_id] || {})[slot.id] || 0
  const laneCount = laneCounts.value[slot.instrument_id] || 1
  const laneH = Math.max(30, Math.floor((rowHeight.value - 8) / laneCount))
  const top = lane * laneH + 4

  return { left: left + 'px', width: Math.max(3, right - left) + 'px', top: top + 'px', height: Math.max(24, laneH - 4) + 'px' }
}

const taskIconMap: Record<string, Component> = {
  FFKF_001: ExperimentOutlined,
  QCFA_001: EditOutlined,
  FFYZ_001: CheckSquareOutlined,
  SJCL_001: DotChartOutlined,
  ZXBG_001: FileTextOutlined,
}
function getTaskIcon(code: string | null | undefined) { return code ? (taskIconMap[code] || null) : null }
function getTaskTypeLabel(code: string | null | undefined) { return code ? (taskTypeMap.value[code] || code) : '' }
function getSlotStatusMeta(status: string): StatusMeta {
  return slotStatusMetaMap[status] || { key: 'scheduled', label: status || '待执行' }
}
function getInstrumentStatusMeta(status: string): InstrumentStatusMeta {
  return instrumentStatusMetaMap[status] || { key: 'unknown', label: status || '未知' }
}
function getBarProjectText(slot: TimeSlot) {
  return slot.project_code || '-'
}
function getBarTaskText(slot: TimeSlot) {
  const taskName = slot.task_name || '-'
  const ownerName = slot.assignee_name || '-'
  const delayText = hasDelay(slot) ? ` · 延期${slot.delay_hours || ''}h` : ''
  return `${taskName} · ${ownerName}${delayText}`
}
function isCompactBar(slot: TimeSlot, quarter?: number) {
  if (viewMode.value === 'week') return false
  const style = getBarS…1677 tokens truncated…wMode.value === 'week' && quarter !== undefined) {
    let quarterStart: dayjs.Dayjs | null = null
    let quarterEnd: dayjs.Dayjs | null = null
    for (const col of cols) {
      const qStart = col.start.hour(getSegmentStartHour(quarter))
      const qEnd = col.start.hour(getSegmentEndHour(quarter))
      if (end.isAfter(qStart) && start.isBefore(qEnd)) {
        if (!quarterStart) quarterStart = qStart
        quarterEnd = qEnd
      }
    }
    if (!quarterStart || !quarterEnd) return null
    visibleStart = visibleStart.isAfter(quarterStart) ? visibleStart : quarterStart
    visibleEnd = visibleEnd.isBefore(quarterEnd) ? visibleEnd : quarterEnd
  }

  return visibleEnd.isAfter(visibleStart) ? [visibleStart, visibleEnd] : null
}
function getDelayText(slot: TimeSlot) {
  const hoursText = slot.delay_hours ? `${slot.delay_hours}h` : ''
  return [hoursText, slot.delay_reason || '未填写原因'].filter(Boolean).join(' · ')
}

function statusLabel(s: string) {
  return getSlotStatusMeta(s).label
}

function showTooltip(slot: GanttSlot, e: MouseEvent) {
  hoveredSlot.value = slot
  tooltipX.value = e.clientX + 12
  tooltipY.value = e.clientY - 100
}
function hideTooltip() { hoveredSlot.value = null }

function toDisplaySlots(sourceSlots: TimeSlot[]): TimeSlot[] {
  return sourceSlots.flatMap(slot => {
    if (slot.status !== 'completed') return [slot]
    if (!slot.actual_start || !slot.actual_end) return []
    return [{
      ...slot,
      plan_start: slot.actual_start,
      plan_end: slot.actual_end,
    }]
  })
}

function mergeContinuousSlots(sourceSlots: TimeSlot[]): GanttSlot[] {
  const sortedSlots = [...sourceSlots].sort((a, b) => {
    if (a.instrument_id !== b.instrument_id) return a.instrument_id - b.instrument_id
    const startDiff = dayjs(a.plan_start).valueOf() - dayjs(b.plan_start).valueOf()
    if (startDiff !== 0) return startDiff
    return a.id - b.id
  })

  const merged: GanttSlot[] = []
  for (const slot of sortedSlots) {
    const lastSlot = merged[merged.length - 1]
    if (lastSlot && canMergeSlots(lastSlot, slot)) {
      lastSlot.plan_end = slot.plan_end
      lastSlot.actual_end = slot.actual_end || lastSlot.actual_end
      lastSlot.mergedSlotIds = [...(lastSlot.mergedSlotIds || [lastSlot.id]), slot.id]
      continue
    }
    merged.push({ ...slot, mergedSlotIds: [slot.id] })
  }
  return merged
}

function canMergeSlots(current: GanttSlot, next: TimeSlot) {
  return current.instrument_id === next.instrument_id
    && current.task_id === next.task_id
    && current.status === next.status
    && current.tier === next.tier
    && dayjs(current.plan_end).isSame(dayjs(next.plan_start))
}

async function switchView(mode: 'day' | 'week' | 'month') {
  viewMode.value = mode
  if (mode === 'month') cursorDate.value = dayjs().startOf('month')
  else if (mode === 'week') cursorDate.value = dayjs().startOf('week')
  else cursorDate.value = dayjs().startOf('day')
  updateRowHeight()
  await recalc()
  if (mode === 'day') await centerGanttTimelineOnCurrentTime(containerRef, colWidth)
}

function goPrev() {
  if (viewMode.value === 'day') cursorDate.value = cursorDate.value.subtract(1, 'day')
  else if (viewMode.value === 'week') cursorDate.value = cursorDate.value.subtract(1, 'week')
  else cursorDate.value = cursorDate.value.subtract(1, 'month')
}

function goNext() {
  if (viewMode.value === 'day') cursorDate.value = cursorDate.value.add(1, 'day')
  else if (viewMode.value === 'week') cursorDate.value = cursorDate.value.add(1, 'week')
  else cursorDate.value = cursorDate.value.add(1, 'month')
}

async function goToday() {
  if (viewMode.value === 'month') cursorDate.value = dayjs().startOf('month')
  else if (viewMode.value === 'week') cursorDate.value = dayjs().startOf('week')
  else cursorDate.value = dayjs().startOf('day')
  await recalc()
  if (viewMode.value === 'day') await centerGanttTimelineOnCurrentTime(containerRef, colWidth)
}

async function recalc() {
  await nextTick()
  await new Promise<void>(resolve => {
    setTimeout(() => {
      if (containerRef.value && containerRef.value.clientHeight > 0) {
        computeLanes()
        updateRowHeight()
        const available = containerRef.value.clientWidth - LEFT_WIDTH - 2
        const cols = viewMode.value === 'day' ? 24 : viewMode.value === 'week' ? 7 : cursorDate.value.daysInMonth()
        colWidth.value = Math.max(MIN_COL_WIDTH, available / cols)
        getMaxVerticalScroll()
      }
      resolve()
    }, 50)
  })
}

function updateRowHeight() {
  rowHeight.value = viewMode.value === 'week' ? WEEK_QUARTER_ROW_HEIGHT : ENTITY_ROW_HEIGHT
}

async function fetchData(silent = false) {
  if (!silent) loading.value = true
  try {
    const [insts, timeslots, types] = await Promise.all([getInstruments(), getTimeslots(), getTaskTypes()])
    instruments.value = insts
    slots.value = timeslots
    const map: Record<string, string> = {}
    types.forEach((t: TaskTypeConfig) => { map[t.code] = t.name })
    taskTypeMap.value = map
  } catch { if (!silent) message.error('加载数据失败') }
  finally {
    if (!silent) loading.value = false
    await nextTick()
    await recalc()
    if (viewMode.value === 'day') await centerGanttTimelineOnCurrentTime(containerRef, colWidth)
    if (isFullscreen.value && autoScrollEnabled.value) scheduleAutoScrollStart()
  }
}

