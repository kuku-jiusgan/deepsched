import { computed, ref, unref, type CSSProperties, type Ref } from 'vue'
import dayjs, { type Dayjs } from 'dayjs'

export type HumanGanttViewMode = 'day' | 'week' | 'month'

export interface HumanGanttSlot {
  id: number
  assignee_id?: number | null
  plan_start: string
  plan_end: string
}

export interface HumanGanttUser {
  id: number
  display_name?: string
  username?: string
  is_active?: boolean
}

export interface HumanGanttTimeColumn {
  key: string
  label: string
  subLabel: string
  isWeekend: boolean
  isToday: boolean
  start: Dayjs
  end: Dayjs
}

export interface HumanGanttLaneRow<User extends HumanGanttUser> {
  key: string
  user: User
  userId: number
  lane: number
  laneCount: number
  isFirstLane: boolean
  isLastLane: boolean
}

export interface HumanGanttVisibleInterval {
  start: Dayjs
  end: Dayjs
  startRatio: number
  endRatio: number
}

export interface HumanGanttOptions {
  initialViewMode?: HumanGanttViewMode
  initialCursorDate?: Dayjs | Date | string
  colWidth?: number
  rowHeight?: number
  laneGap?: number
  minBarWidth?: number
  includeInactiveUsers?: boolean
}

export interface HumanGanttComposable<
  Slot extends HumanGanttSlot,
  User extends HumanGanttUser,
> {
  viewMode: Ref<HumanGanttViewMode>
  cursorDate: Ref<Dayjs>
  periodStart: Readonly<Ref<Dayjs>>
  periodEnd: Readonly<Ref<Dayjs>>
  periodLabel: Readonly<Ref<string>>
  timeColumns: Readonly<Ref<HumanGanttTimeColumn[]>>
  totalWidth: Readonly<Ref<number>>
  visibleUsers: Readonly<Ref<User[]>>
  laneRows: Readonly<Ref<HumanGanttLaneRow<User>[]>>
  flatRows: Readonly<Ref<HumanGanttLaneRow<User>[]>>
  getSlotsForRow: (row: HumanGanttLaneRow<User> | User | number) => Slot[]
  getVisibleInterval: (slot: Slot) => HumanGanttVisibleInterval | null
  getBarStyle: (slot: Slot, row?: HumanGanttLaneRow<User>) => CSSProperties
  switchView: (mode: HumanGanttViewMode) => void
  goPrev: () => void
  goNext: () => void
  goToday: () => void
}

type MaybeRefReadonly<T> = T | Readonly<Ref<T>>

const DEFAULT_COLUMN_WIDTH = 140
const DEFAULT_ROW_HEIGHT = 40
const DEFAULT_LANE_GAP = 4
const DEFAULT_MIN_BAR_WIDTH = 3
const WEEKDAY_LABELS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const SHORT_WEEKDAY_LABELS = ['日', '一', '二', '三', '四', '五', '六']

export function useHumanGantt<
  Slot extends HumanGanttSlot,
  User extends HumanGanttUser,
>(
  slotsRef: MaybeRefReadonly<readonly Slot[]>,
  usersRef: MaybeRefReadonly<readonly User[]>,
  options: HumanGanttOptions = {},
): HumanGanttComposable<Slot, User> {
  const initialMode = options.initialViewMode ?? 'week'
  const viewMode = ref<HumanGanttViewMode>(initialMode)
  const cursorDate = ref(normalizeCursorDate(dayjs(options.initialCursorDate), initialMode))
  const colWidth = options.colWidth ?? DEFAULT_COLUMN_WIDTH
  const rowHeight = options.rowHeight ?? DEFAULT_ROW_HEIGHT
  const laneGap = options.laneGap ?? DEFAULT_LANE_GAP
  const minBarWidth = options.minBarWidth ?? DEFAULT_MIN_BAR_WIDTH

  const periodStart = computed(() => getPeriodStart(cursorDate.value, viewMode.value))
  const periodEnd = computed(() => getPeriodEnd(cursorDate.value, viewMode.value))
  const periodLabel = computed(() => formatPeriodLabel(periodStart.value, periodEnd.value, viewMode.value))

  const timeColumns = computed<HumanGanttTimeColumn[]>(() => {
    const todayKey = dayjs().format('YYYY-MM-DD')
    if (viewMode.value === 'day') return createDayColumns(periodStart.value, todayKey)
    if (viewMode.value === 'week') return createDateColumns(periodStart.value, 7, todayKey, true)
    return createDateColumns(periodStart.value, periodStart.value.daysInMonth(), todayKey, false)
  })

  const totalWidth = computed(() => timeColumns.value.length * colWidth)

  const visibleSlots = computed(() => unref(slotsRef).filter(slot => {
    if (slot.assignee_id == null || !isValidSlotRange(slot)) return false
    return overlapsRange(dayjs(slot.plan_start), dayjs(slot.plan_end), periodStart.value, periodEnd.value)
  }))

  const visibleUsers = computed<User[]>(() => {
    const assignedUserIds = new Set(visibleSlots.value.map(slot => slot.assignee_id as number))
    return unref(usersRef).filter(user => {
      if (user.is_active !== false) return true
      return options.includeInactiveUsers !== false && assignedUserIds.has(user.id)
    }) as User[]
  })

  const slotsByUser = computed(() => {
    const grouped = new Map<number, Slot[]>()
    for (const slot of visibleSlots.value) {
      const userId = slot.assignee_id
      if (userId == null) continue
      const userSlots = grouped.get(userId) ?? []
      userSlots.push(slot)
      grouped.set(userId, userSlots)
    }
    for (const userSlots of grouped.values()) userSlots.sort(compareSlots)
    return grouped
  })

  const laneAssignments = computed(() => {
    const assignments = new Map<number, Map<number, number>>()
    const laneCounts = new Map<number, number>()

    for (const user of visibleUsers.value) {
      const userAssignments = new Map<number, number>()
      const laneEnds: number[] = []
      for (const slot of slotsByUser.value.get(user.id) ?? []) {
        const start = dayjs(slot.plan_start).valueOf()
        const end = dayjs(slot.plan_end).valueOf()
        const availableLane = laneEnds.findIndex(laneEnd => start >= laneEnd)
        const lane = availableLane === -1 ? laneEnds.length : availableLane
        laneEnds[lane] = end
        userAssignments.set(slot.id, lane)
      }
      assignments.set(user.id, userAssignments)
      laneCounts.set(user.id, Math.max(1, laneEnds.length))
    }

    return { assignments, laneCounts }
  })

  const laneRows = computed<HumanGanttLaneRow<User>[]>(() => visibleUsers.value.flatMap(user => {
    const laneCount = laneAssignments.value.laneCounts.get(user.id) ?? 1
    return Array.from({ length: laneCount }, (_, lane) => ({
      key: `${user.id}:${lane}`,
      user,
      userId: user.id,
      lane,
      laneCount,
      isFirstLane: lane === 0,
      isLastLane: lane === laneCount - 1,
    }))
  }))

  function getSlotsForRow(row: HumanGanttLaneRow<User> | User | number): Slot[] {
    const userId = typeof row === 'number' ? row : 'userId' in row ? row.userId : row.id
    const userSlots = slotsByUser.value.get(userId) ?? []
    if (typeof row === 'object' && 'lane' in row) {
      const assignments = laneAssignments.value.assignments.get(userId)
      return userSlots.filter(slot => assignments?.get(slot.id) === row.lane)
    }
    return userSlots
  }

  function getVisibleInterval(slot: Slot): HumanGanttVisibleInterval | null {
    if (!isValidSlotRange(slot)) return null
    const slotStart = dayjs(slot.plan_start)
    const slotEnd = dayjs(slot.plan_end)
    if (!overlapsRange(slotStart, slotEnd, periodStart.value, periodEnd.value)) return null

    const visibleStart = slotStart.isBefore(periodStart.value) ? periodStart.value : slotStart
    const visibleEnd = slotEnd.isAfter(periodEnd.value) ? periodEnd.value : slotEnd
    const duration = Math.max(1, periodEnd.value.diff(periodStart.value, 'millisecond', true))
    return {
      start: visibleStart,
      end: visibleEnd,
      startRatio: visibleStart.diff(periodStart.value, 'millisecond', true) / duration,
      endRatio: visibleEnd.diff(periodStart.value, 'millisecond', true) / duration,
    }
  }

  function getBarStyle(slot: Slot, row?: HumanGanttLaneRow<User>): CSSProperties {
    const interval = getVisibleInterval(slot)
    if (!interval) return { display: 'none' }

    const left = getTimelinePosition(interval.start, timeColumns.value, colWidth)
    const right = getTimelinePosition(interval.end, timeColumns.value, colWidth)
    if (left == null || right == null) return { display: 'none' }

    const userId = slot.assignee_id ?? -1
    const lane = laneAssignments.value.assignments.get(userId)?.get(slot.id) ?? 0
    if (row && row.lane !== lane) return { display: 'none' }

    const laneCount = row?.laneCount ?? laneAssignments.value.laneCounts.get(userId) ?? 1
    const laneHeight = Math.max(1, (rowHeight - laneGap * (laneCount + 1)) / laneCount)
    const top = row ? laneGap : laneGap + lane * (laneHeight + laneGap)

    return {
      left: `${left}px`,
      width: `${Math.max(minBarWidth, right - left)}px`,
      top: `${top}px`,
      height: `${Math.max(1, row ? rowHeight - laneGap * 2 : laneHeight)}px`,
    }
  }

  function switchView(mode: HumanGanttViewMode) {
    viewMode.value = mode
    cursorDate.value = normalizeCursorDate(dayjs(), mode)
  }

  function goPrev() {
    cursorDate.value = moveCursor(cursorDate.value, viewMode.value, -1)
  }

  function goNext() {
    cursorDate.value = moveCursor(cursorDate.value, viewMode.value, 1)
  }

  function goToday() {
    cursorDate.value = normalizeCursorDate(dayjs(), viewMode.value)
  }

  return {
    viewMode,
    cursorDate,
    periodStart,
    periodEnd,
    periodLabel,
    timeColumns,
    totalWidth,
    visibleUsers,
    laneRows,
    flatRows: laneRows,
    getSlotsForRow,
    getVisibleInterval,
    getBarStyle,
    switchView,
    goPrev,
    goNext,
    goToday,
  }
}

function normalizeCursorDate(value: Dayjs, mode: HumanGanttViewMode): Dayjs {
  const safeValue = value.isValid() ? value : dayjs()
  return getPeriodStart(safeValue, mode)
}

function getPeriodStart(cursor: Dayjs, mode: HumanGanttViewMode): Dayjs {
  if (mode === 'month') return cursor.startOf('month')
  if (mode === 'week') return cursor.startOf('week')
  return cursor.startOf('day')
}

function getPeriodEnd(cursor: Dayjs, mode: HumanGanttViewMode): Dayjs {
  const start = getPeriodStart(cursor, mode)
  if (mode === 'month') return start.add(1, 'month')
  if (mode === 'week') return start.add(1, 'week')
  return start.add(1, 'day')
}

function formatPeriodLabel(start: Dayjs, end: Dayjs, mode: HumanGanttViewMode): string {
  if (mode === 'day') return start.format('YYYY年MM月DD日')
  if (mode === 'week') return `${start.format('MM/DD')} - ${end.subtract(1, 'day').format('MM/DD')}`
  return start.format('YYYY年MM月')
}

function createDayColumns(start: Dayjs, todayKey: string): HumanGanttTimeColumn[] {
  return Array.from({ length: 24 }, (_, hour) => {
    const columnStart = start.add(hour, 'hour')
    return {
      key: `h${hour}`,
      label: `${String(hour).padStart(2, '0')}:00`,
      subLabel: '',
      isWeekend: false,
      isToday: columnStart.format('YYYY-MM-DD') === todayKey,
      start: columnStart,
      end: columnStart.add(1, 'hour'),
    }
  })
}

function createDateColumns(
  start: Dayjs,
  count: number,
  todayKey: string,
  isWeekView: boolean,
): HumanGanttTimeColumn[] {
  return Array.from({ length: count }, (_, index) => {
    const columnStart = start.add(index, 'day').startOf('day')
    return {
      key: `d${index}`,
      label: isWeekView ? WEEKDAY_LABELS[columnStart.day()] : `${columnStart.date()}日`,
      subLabel: isWeekView ? columnStart.format('MM/DD') : `周${SHORT_WEEKDAY_LABELS[columnStart.day()]}`,
      isWeekend: columnStart.day() === 0 || columnStart.day() === 6,
      isToday: columnStart.format('YYYY-MM-DD') === todayKey,
      start: columnStart,
      end: columnStart.add(1, 'day'),
    }
  })
}

function compareSlots<Slot extends HumanGanttSlot>(left: Slot, right: Slot): number {
  const startDifference = dayjs(left.plan_start).valueOf() - dayjs(right.plan_start).valueOf()
  return startDifference || dayjs(left.plan_end).valueOf() - dayjs(right.plan_end).valueOf() || left.id - right.id
}

function isValidSlotRange(slot: HumanGanttSlot): boolean {
  const start = dayjs(slot.plan_start)
  const end = dayjs(slot.plan_end)
  return start.isValid() && end.isValid() && end.isAfter(start)
}

function overlapsRange(start: Dayjs, end: Dayjs, rangeStart: Dayjs, rangeEnd: Dayjs): boolean {
  return end.isAfter(rangeStart) && start.isBefore(rangeEnd)
}

function getTimelinePosition(
  value: Dayjs,
  columns: readonly HumanGanttTimeColumn[],
  colWidth: number,
): number | null {
  if (!columns.length) return null
  const timelineStart = columns[0].start
  const timelineEnd = columns[columns.length - 1].end
  if (value.isBefore(timelineStart) || value.isAfter(timelineEnd)) return null
  if (value.isSame(timelineEnd)) return columns.length * colWidth

  const columnIndex = columns.findIndex(column => !value.isBefore(column.start) && value.isBefore(column.end))
  if (columnIndex === -1) return null
  const column = columns[columnIndex]
  const duration = Math.max(1, column.end.diff(column.start, 'millisecond', true))
  const offset = value.diff(column.start, 'millisecond', true)
  return (columnIndex + offset / duration) * colWidth
}

function moveCursor(cursor: Dayjs, mode: HumanGanttViewMode, amount: -1 | 1): Dayjs {
  if (mode === 'month') return cursor.add(amount, 'month').startOf('month')
  if (mode === 'week') return cursor.add(amount, 'week').startOf('week')
  return cursor.add(amount, 'day').startOf('day')
}