<template>
  <div class="gantt-page" :class="{ 'is-fullscreen': isFullscreen }">
    <div class="page-header">
      <h2>仪器甘特图</h2>
      <p>按仪器查看排程负荷、运行状态与延期风险</p>
    </div>

    <div class="action-bar" :class="{ 'is-screen-toolbar': isFullscreen }">
      <a-button-group>
        <a-button :type="viewMode === 'day' ? 'primary' : 'default'" @click="switchView('day')">日</a-button>
        <a-button :type="viewMode === 'week' ? 'primary' : 'default'" @click="switchView('week')">周</a-button>
        <a-button :type="viewMode === 'month' ? 'primary' : 'default'" @click="switchView('month')">月</a-button>
      </a-button-group>
      <a-button @click="goPrev"><LeftOutlined /></a-button>
      <span class="period-label">{{ periodLabel }}</span>
      <a-button @click="goNext"><RightOutlined /></a-button>
      <a-button @click="goToday">今天</a-button>
      <a-button @click="fetchData"><ReloadOutlined /> 刷新</a-button>
      <a-button @click="toggleFullscreen"><component :is="isFullscreen ? FullscreenExitOutlined : FullscreenOutlined" /> 全屏</a-button>
      <span class="auto-scroll-control">
        <a-switch v-model:checked="autoScrollEnabled" size="small" />
        <span>全屏自动滚动</span>
      </span>
    </div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 80px auto" />

    <div v-else-if="!instruments.length" style="padding: 80px; text-align: center; color: #94a3b8">
      暂无仪器数据，请先在「基础资源台账」中添加仪器并生成排程
    </div>

    <div
      v-else
      class="gantt-container"
      :class="{ 'is-week-view': viewMode === 'week' }"
      ref="containerRef"
    >
      <div class="gantt-left">
        <div class="gantt-header-cell">仪器</div>
        <div v-for="row in flatRows" :key="'l-' + row.inst.id + '-q' + row.quarter"
          class="gantt-left-row" :class="{ 'is-subrow': row.isSubrow, 'is-last': row.isLast || (viewMode === 'week' && !row.isSubrow), 'has-segment-rail': viewMode === 'week' && !row.isSubrow }"
          :style="getLeftRowStyle(row)">
          <template v-if="!row.isSubrow || viewMode !== 'week'">
            <div class="inst-meta-line">
              <span class="inst-code">{{ row.inst.code }}</span>
              <span class="inst-status-chip" :class="'inst-status-' + getInstrumentStatusMeta(row.inst.status).key">
                {{ getInstrumentStatusMeta(row.inst.status).label }}
              </span>
            </div>
            <div class="inst-name">{{ row.inst.name }}</div>
            <div class="inst-model" v-if="row.inst.model">{{ row.inst.model }}</div>
            <div v-if="viewMode === 'week'" class="segment-rail" aria-label="每日 8 小时分段">
              <span v-for="segment in WEEK_SEGMENT_COUNT" :key="segment" class="segment-rail-label">
                {{ getSegmentLabel(segment - 1) }}
              </span>
            </div>
          </template>
        </div>
      </div>

      <div class="gantt-right" ref="rightRef">
        <div class="gantt-timeline-header" :style="{ width: totalWidth + 'px' }">
          <div v-for="col in timeColumns" :key="col.key" class="gantt-col-header" :style="{ width: colWidth + 'px' }"
            :class="{ 'is-weekend': col.isWeekend, 'is-today': col.isToday, 'is-current': col.isCurrent }">
            <div class="col-label-primary">{{ col.label }}</div>
            <div v-if="col.subLabel" class="col-label-sub">{{ col.subLabel }}</div>
          </div>
        </div>
        <div class="gantt-timeline-body" :style="{ width: totalWidth + 'px' }">
          <div v-for="row in flatRows" :key="'r-' + row.inst.id + '-q' + row.quarter"
            class="gantt-entity-row" :class="{ 'is-subrow': row.isSubrow, 'is-last': row.isLast || (viewMode === 'week' && !row.isSubrow) }"
            :style="{ height: Math.max(12, rowHeight) + 'px' }">
            <div v-for="col in timeColumns" :key="col.key" class="gantt-grid-cell"
              :style="{ width: colWidth + 'px' }" :class="{ 'is-weekend': col.isWeekend, 'is-today': col.isToday, 'is-current': col.isCurrent }" />
            <div v-for="slot in getSlotsForQuarter(row.inst.id, row.quarter)" :key="slot.id"
              class="gantt-bar" :class="getBarClasses(slot, row.quarter)"
              :style="getBarStyle(slot, row.quarter)"
              @mouseenter="e => showTooltip(slot, e)"
              @mouseleave="hideTooltip">
              <span v-if="hasDelay(slot)" class="bar-delay-segment" :style="getDelaySegmentStyle(slot, row.quarter)">
                <span class="bar-delay-badge">延</span>
              </span>
              <span v-if="getWeekBarDisplay(slot, row.quarter).showIcon" class="bar-tag">
                <span class="bar-status-dot"></span>
                <component v-if="getTaskIcon(slot.task_type)" :is="getTaskIcon(slot.task_type)" />
              </span>
              <span v-if="getWeekBarDisplay(slot, row.quarter).showLabel" class="bar-label">
                <span v-if="getWeekBarDisplay(slot, row.quarter).projectText" class="bar-project">{{ getWeekBarDisplay(slot, row.quarter).projectText }}</span>
                <span v-if="getWeekBarDisplay(slot, row.quarter).taskText" class="bar-task">{{ getWeekBarDisplay(slot, row.quarter).taskText }}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="isFullscreen && autoScrollEnabled && !hasVerticalOverflow" class="auto-scroll-note">
        当前仪器已全部展示，无需滚动
      </div>
    </div>

    <div v-if="hoveredSlot" class="gantt-tooltip" :style="tooltipStyle">
      <div class="tooltip-title">{{ hoveredSlot.task_name }}</div>
      <div class="tooltip-row"><span>工序</span>{{ getTaskTypeLabel(hoveredSlot.task_type) }}</div>
      <div class="tooltip-row"><span>项目</span>{{ getBarProjectText(hoveredSlot) }}</div>
      <div class="tooltip-row"><span>负责人</span>{{ hoveredSlot.assignee_name || '-' }}</div>
      <div class="tooltip-row"><span>开始</span>{{ dayjs(hoveredSlot.plan_start).format('MM-DD HH:mm') }}</div>
      <div class="tooltip-row"><span>结束</span>{{ dayjs(hoveredSlot.plan_end).format('MM-DD HH:mm') }}</div>
      <div class="tooltip-row"><span>状态</span>{{ statusLabel(hoveredSlot.status) }}</div>
      <div v-if="hasDelay(hoveredSlot)" class="tooltip-row is-delay"><span>延期</span>{{ getDelayText(hoveredSlot) }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import type { CSSProperties, Component } from 'vue'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined, ReloadOutlined, FullscreenOutlined, FullscreenExitOutlined, ExperimentOutlined, EditOutlined, CheckSquareOutlined, DotChartOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getInstruments, getTimeslots, getTaskTypes, type TaskTypeConfig } from '@/services/api'
import type { Instrument, TimeSlot } from '@/types'
import dayjs from 'dayjs'

const LEFT_WIDTH = 250
const HEADER_HEIGHT = 50
const WEEK_QUARTER_ROW_HEIGHT = 42
const WEEK_SEGMENT_COUNT = 3
const WEEK_SEGMENT_HOURS = 8
const WEEK_SEGMENT_SECONDS = WEEK_SEGMENT_HOURS * 60 * 60
const ENTITY_ROW_HEIGHT = 72
const MIN_COL_WIDTH = 72
const AUTO_SCROLL_STEP_PX = 1.2
const AUTO_SCROLL_INTERVAL_MS = 30
const AUTO_SCROLL_EDGE_PAUSE_MS = 1200
const AUTO_SCROLL_START_DELAY_MS = 500
const AUTO_SCROLL_START_RETRY_MS = 220
const AUTO_SCROLL_START_MAX_RETRIES = 10
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
const autoScrollEnabled = ref(true)
const hasVerticalOverflow = ref(false)
const hoveredSlot = ref<TimeSlot | null>(null)
const tooltipX = ref(0)
const tooltipY = ref(0)
const tooltipStyle = computed(() => ({ left: tooltipX.value + 'px', top: tooltipY.value + 'px' }))
const containerRef = ref<HTMLElement | null>(null)
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

function computeLanes() {
  const map: Record<number, Record<number, number>> = {}
  const counts: Record<number, number> = {}
  for (const inst of instruments.value) {
    const instSlots = slots.value.filter(s => s.instrument_id === inst.id).sort((a, b) => dayjs(a.plan_start).valueOf() - dayjs(b.plan_start).valueOf())
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

function getBarClasses(slot: TimeSlot, quarter?: number) {
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
  return slots.value.filter(s => s.instrument_id === instId)
}

function getBarStyle(slot: TimeSlot, quarter?: number) {
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
  const style = getBarStyle(slot, quarter)
  const rawWidth = typeof style.width === 'string' ? Number.parseFloat(style.width) : Number(style.width)
  return Number.isFinite(rawWidth) && rawWidth < 68
}
function getWeekBarDisplay(slot: TimeSlot, quarter?: number): WeekBarDisplay {
  const fullDisplay = {
    showIcon: true,
    showLabel: true,
    projectText: getBarProjectText(slot),
    taskText: getBarTaskText(slot),
  }
  if (viewMode.value !== 'week' || quarter === undefined) return fullDisplay

  const current = getVisibleWeekSegments(slot).find(segment => segment.quarter === quarter)
  if (!current || current.width < WEEK_BAR_TINY_WIDTH) {
    return { showIcon: false, showLabel: false, projectText: '', taskText: '' }
  }

  const segments = getVisibleWeekSegments(slot).filter(segment => segment.width >= WEEK_BAR_TINY_WIDTH)
  if (!segments.length) return { showIcon: false, showLabel: false, projectText: '', taskText: '' }

  const roles = assignWeekBarRoles(segments)
  const role = roles[quarter]
  const projectCode = getBarProjectText(slot)
  const taskName = slot.task_name || ''
  const ownerName = slot.assignee_name || ''
  const delayText = hasDelay(slot) ? `延期${slot.delay_hours || ''}h` : ''
  const projectAndOwner = [projectCode, ownerName].filter(Boolean).join(' · ')
  const taskOrDelay = [taskName, delayText].filter(Boolean).join(' · ')
  const showIcon = current.width >= WEEK_BAR_ICON_WIDTH && role !== 'none'

  if (role === 'project') {
    return {
      showIcon,
      showLabel: true,
      projectText: projectAndOwner || projectCode,
      taskText: current.width >= WEEK_BAR_FULL_WIDTH ? taskOrDelay : '',
    }
  }
  if (role === 'task') {
    return {
      showIcon,
      showLabel: Boolean(projectAndOwner || taskName || projectCode),
      projectText: projectAndOwner || projectCode,
      taskText: taskName || delayText,
    }
  }
  if (role === 'owner') {
    return {
      showIcon,
      showLabel: Boolean(projectAndOwner || taskOrDelay || projectCode),
      projectText: projectAndOwner || projectCode,
      taskText: taskOrDelay,
    }
  }

  return { showIcon: false, showLabel: false, projectText: '', taskText: '' }
}
function assignWeekBarRoles(segments: WeekBarSegment[]) {
  const roles: Record<number, 'project' | 'task' | 'owner' | 'none'> = {}
  segments.forEach(segment => { roles[segment.quarter] = 'none' })
  const roleTargets = [...segments].sort((a, b) => a.quarter - b.quarter)
  if (roleTargets.length === 1) {
    roles[roleTargets[0].quarter] = 'project'
    return roles
  }
  if (roleTargets.length === 2) {
    roles[roleTargets[0].quarter] = 'project'
    roles[roleTargets[1].quarter] = 'task'
    return roles
  }
  roles[roleTargets[0].quarter] = 'project'
  roles[roleTargets[1].quarter] = 'task'
  roles[roleTargets[2].quarter] = 'owner'
  return roles
}
function getVisibleWeekSegments(slot: TimeSlot): WeekBarSegment[] {
  const result: WeekBarSegment[] = []
  for (let quarter = 0; quarter < WEEK_SEGMENT_COUNT; quarter++) {
    const visibleSeconds = getVisibleSecondsInQuarter(slot, quarter)
    if (visibleSeconds <= 0) continue
    const style = getBarStyle(slot, quarter)
    const width = parseStyleWidth(style.width)
    if (!Number.isFinite(width) || width <= 0) continue
    result.push({ quarter, width, visibleSeconds })
  }
  return result
}
function parseStyleWidth(width: CSSProperties['width']) {
  if (typeof width === 'number') return width
  if (typeof width === 'string') return Number.parseFloat(width)
  return 0
}
function getVisibleSecondsInQuarter(slot: TimeSlot, quarter: number) {
  const start = dayjs(slot.plan_start)
  const end = dayjs(slot.plan_end)
  const cols = timeColumns.value
  let totalSeconds = 0
  for (const col of cols) {
    const qStart = col.start.hour(getSegmentStartHour(quarter))
    const qEnd = col.start.hour(getSegmentEndHour(quarter))
    if (!end.isAfter(qStart) || !start.isBefore(qEnd)) continue
    const visibleStart = start.isAfter(qStart) ? start : qStart
    const visibleEnd = end.isBefore(qEnd) ? end : qEnd
    if (visibleEnd.isAfter(visibleStart)) {
      totalSeconds += visibleEnd.diff(visibleStart, 'second', true)
    }
  }
  return totalSeconds
}
function hasDelay(slot: TimeSlot) {
  const delayHours = Number(slot.delay_hours || 0)
  const hasDelayReport = Boolean(slot.delay_reason) || delayHours > 0
  if (!hasDelayReport) return false
  if (DELAY_PROBLEM_STATUSES.has(slot.status)) return true
  return slot.status === 'running' && Boolean(slot.actual_start)
}
function getDelaySegmentStyle(slot: TimeSlot, quarter?: number): CSSProperties {
  if (!slot.delay_hours || slot.delay_hours <= 0) return { display: 'none' }
  const start = dayjs(slot.plan_start)
  const end = dayjs(slot.plan_end)
  const delayStart = end.subtract(slot.delay_hours, 'hour')
  const visibleRange = getVisibleBarRange(start, end, quarter)
  if (!visibleRange) return { display: 'none' }
  if (isFullDelaySlot(slot)) return { left: '0', width: '100%' }

  const [visibleStart, visibleEnd] = visibleRange
  const segmentStart = delayStart.isAfter(visibleStart) ? delayStart : visibleStart
  const segmentEnd = end.isBefore(visibleEnd) ? end : visibleEnd
  if (!segmentEnd.isAfter(segmentStart)) return { display: 'none' }

  const visibleSeconds = visibleEnd.diff(visibleStart, 'second', true)
  const leftPercent = segmentStart.diff(visibleStart, 'second', true) / Math.max(1, visibleSeconds) * 100
  const widthPercent = segmentEnd.diff(segmentStart, 'second', true) / Math.max(1, visibleSeconds) * 100
  return {
    left: `${leftPercent}%`,
    width: `${widthPercent}%`,
    minWidth: '8px',
    maxWidth: `calc(${100 - leftPercent}% - 1px)`,
  }
}
function isFullDelaySlot(slot: TimeSlot) {
  if (!slot.delay_hours || slot.delay_hours <= 0) return false
  const slotStart = dayjs(slot.plan_start)
  const slotEnd = dayjs(slot.plan_end)
  const slotDurationHours = slotEnd.diff(slotStart, 'hour', true)
  if (slot.delay_hours >= slotDurationHours) return true
  return slots.value.some(other =>
    other.id !== slot.id &&
    other.task_id === slot.task_id &&
    Boolean(other.plan_end) &&
    !dayjs(other.plan_end).isAfter(slotStart)
  )
}
function getVisibleBarRange(start: dayjs.Dayjs, end: dayjs.Dayjs, quarter?: number): [dayjs.Dayjs, dayjs.Dayjs] | null {
  const cols = timeColumns.value
  if (!cols.length) return null
  let visibleStart = start.isAfter(cols[0].start) ? start : cols[0].start
  let visibleEnd = end.isBefore(cols[cols.length - 1].end) ? end : cols[cols.length - 1].end

  if (viewMode.value === 'week' && quarter !== undefined) {
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

function showTooltip(slot: TimeSlot, e: MouseEvent) {
  hoveredSlot.value = slot
  tooltipX.value = e.clientX + 12
  tooltipY.value = e.clientY - 100
}
function hideTooltip() { hoveredSlot.value = null }

function switchView(mode: 'day' | 'week' | 'month') {
  viewMode.value = mode
  if (mode === 'month') cursorDate.value = dayjs().startOf('month')
  else if (mode === 'week') cursorDate.value = dayjs().startOf('week')
  else cursorDate.value = dayjs().startOf('day')
  updateRowHeight()
  recalc()
  if (mode === 'day') scrollToNow()
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

function goToday() {
  if (viewMode.value === 'month') cursorDate.value = dayjs().startOf('month')
  else if (viewMode.value === 'week') cursorDate.value = dayjs().startOf('week')
  else cursorDate.value = dayjs().startOf('day')
  recalc()
  if (viewMode.value === 'day') scrollToNow()
}


function scrollToNow() {
  if (viewMode.value !== 'day' || !containerRef.value) return
  nextTick(() => {
    const container = containerRef.value
    if (!container) return
    const hour = dayjs().hour()
    const x = hour * colWidth.value
    container.scrollLeft = Math.max(0, x - container.clientWidth / 2)
  })
}

function recalc() {
  nextTick(() => {
    setTimeout(() => {
      if (!containerRef.value || containerRef.value.clientHeight <= 0) return
      computeLanes()
      updateRowHeight()
      const available = containerRef.value.clientWidth - LEFT_WIDTH - 2
      const cols = viewMode.value === 'day' ? 24 : viewMode.value === 'week' ? 7 : cursorDate.value.daysInMonth()
      colWidth.value = Math.max(MIN_COL_WIDTH, available / cols)
      getMaxVerticalScroll()
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
    recalc()
    if (viewMode.value === 'day') scrollToNow()
    if (isFullscreen.value && autoScrollEnabled.value) scheduleAutoScrollStart()
  }
}

let resizeObserver: ResizeObserver | null = null

let refreshTimer: ReturnType<typeof setInterval> | null = null


let autoScrollTimer: ReturnType<typeof setInterval> | null = null
let autoScrollRetryTimer: ReturnType<typeof setTimeout> | null = null
let autoScrollDirection = 1
let autoScrollHoldUntil = 0

function toggleFullscreen() {
  if (!isFullscreen.value) {
    autoScrollEnabled.value = true
    document.documentElement.requestFullscreen()
      .catch(() => message.error('浏览器未允许进入全屏'))
  } else {
    stopAutoScroll()
    document.exitFullscreen()
  }
}

function scheduleAutoScrollStart(delay = AUTO_SCROLL_START_DELAY_MS, retryCount = 0) {
  if (autoScrollTimer !== null) return
  if (autoScrollRetryTimer) clearTimeout(autoScrollRetryTimer)
  autoScrollRetryTimer = setTimeout(async () => {
    autoScrollRetryTimer = null
    await nextTick()
    recalc()
    const started = startAutoScroll()
    if (!started && isFullscreen.value && autoScrollEnabled.value && retryCount < AUTO_SCROLL_START_MAX_RETRIES) {
      scheduleAutoScrollStart(AUTO_SCROLL_START_RETRY_MS, retryCount + 1)
    }
  }, delay)
}

function getMaxVerticalScroll() {
  const container = containerRef.value
  if (!container) return 0
  const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight)
  hasVerticalOverflow.value = maxScroll > 2
  return maxScroll
}

function startAutoScroll() {
  if (!containerRef.value || !isFullscreen.value || !autoScrollEnabled.value) {
    getMaxVerticalScroll()
    return false
  }
  if (autoScrollTimer !== null) return true
  if (getMaxVerticalScroll() <= 2) return false
  autoScrollDirection = 1
  autoScrollHoldUntil = performance.now() + 150
  autoScrollTimer = setInterval(runAutoScrollTick, AUTO_SCROLL_INTERVAL_MS)
  return true
}

function runAutoScrollTick() {
  const container = containerRef.value
  if (!container || !autoScrollEnabled.value || !isFullscreen.value) {
    stopAutoScroll()
    return
  }

  const maxScroll = getMaxVerticalScroll()
  if (maxScroll <= 2) {
    stopAutoScroll()
    return
  }

  const now = performance.now()
  if (now < autoScrollHoldUntil) {
    return
  }

  const nextScroll = container.scrollTop + autoScrollDirection * AUTO_SCROLL_STEP_PX

  if (nextScroll >= maxScroll) {
    container.scrollTop = maxScroll
    autoScrollDirection = -1
    autoScrollHoldUntil = now + AUTO_SCROLL_EDGE_PAUSE_MS
  } else if (nextScroll <= 0) {
    container.scrollTop = 0
    autoScrollDirection = 1
    autoScrollHoldUntil = now + AUTO_SCROLL_EDGE_PAUSE_MS
  } else {
    container.scrollTop = nextScroll
  }
}

function stopAutoScroll() {
  if (autoScrollTimer !== null) {
    clearInterval(autoScrollTimer)
    autoScrollTimer = null
  }
  if (autoScrollRetryTimer) {
    clearTimeout(autoScrollRetryTimer)
    autoScrollRetryTimer = null
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  if (isFullscreen.value) {
    autoScrollEnabled.value = true
    scheduleAutoScrollStart()
  } else {
    stopAutoScroll()
  }
  nextTick(() => getMaxVerticalScroll())
}

function handleResize() {
  recalc()
  if (isFullscreen.value && autoScrollEnabled.value && autoScrollTimer === null) {
    scheduleAutoScrollStart(300)
  }
}

onMounted(() => {
  fetchData()
  refreshTimer = setInterval(() => fetchData(true), 30000)
  window.addEventListener('resize', handleResize)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  nextTick(() => {
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(() => {
        if (containerRef.value && containerRef.value.clientHeight > 0) {
          recalc()
          if (isFullscreen.value && autoScrollEnabled.value && autoScrollTimer === null) scheduleAutoScrollStart(300)
        }
      })
      resizeObserver.observe(containerRef.value)
    }
  })
})
watch(autoScrollEnabled, (enabled) => {
  if (!isFullscreen.value) return
  if (enabled) {
    scheduleAutoScrollStart(0)
  } else {
    stopAutoScroll()
  }
})
onUnmounted(() => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  stopAutoScroll()
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
})
</script>

<style scoped>
.gantt-page { display: flex; flex-direction: column; height: calc(100vh - 64px); }

.gantt-page.is-fullscreen {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 9999;
  background: #f6f8fb; padding: 16px; height: 100vh;
}
.gantt-page.is-fullscreen .gantt-container { flex: 1; min-height: 0; }
.gantt-page.is-fullscreen .page-header { display: none; }
.gantt-page.is-fullscreen .action-bar { padding: 0 0 12px 0; }

.period-label {
  min-width: 160px;
  text-align: center;
  font-weight: 600;
  color: #1e293b;
}
.action-bar.is-screen-toolbar {
  align-items: center;
  margin-bottom: 0;
}

.auto-scroll-control {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
}

.gantt-container {
  position: relative;
  display: flex;
  flex: 1;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: auto;
  margin-top: 12px;
  min-height: 0;
  background: #fff;
}

.gantt-left {
  width: 250px;
  min-width: 250px;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  position: sticky;
  left: 0;
  z-index: 3;
}
.gantt-left::-webkit-scrollbar { width: 0; }
.gantt-header-cell {
  position: sticky;
  top: 0;
  z-index: 6;
  height: 50px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  font-weight: 600;
  font-size: 13px;
  color: #475569;
  border-bottom: 1px solid #cbd5e1;
  background: #f1f5f9;
}
.gantt-left-row {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 14px;
  border-bottom: none;
  overflow: hidden;
}
.gantt-left-row.has-segment-rail { padding-right: 62px; }
.gantt-left-row.is-last { border-bottom: 1px solid #cbd5e1; }
.inst-meta-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}
.inst-code {
  display: inline-block;
  flex: 0 1 auto;
  max-width: 100%;
  padding: 2px 6px;
  border-radius: 5px;
  background: #e0f2fe;
  color: #075985;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  white-space: normal;
  overflow-wrap: anywhere;
}
.inst-status-chip {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #475569;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.45;
}
.inst-status-idle { color: #2563eb; background: #eff6ff; border-color: #bfdbfe; }
.inst-status-running { color: #047857; background: #ecfdf5; border-color: #bbf7d0; }
.inst-status-maintenance { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.inst-status-fault { color: #b91c1c; background: #fef2f2; border-color: #fecaca; }
.inst-status-disabled, .inst-status-unknown { color: #64748b; background: #f1f5f9; border-color: #cbd5e1; }
.segment-rail {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 50px;
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  border-left: 1px solid #e2e8f0;
  background: #f8fafc;
}
.segment-rail-label {
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #e2e8f0;
  color: #64748b;
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1;
}
.segment-rail-label:last-child { border-bottom: none; }
.inst-name {
  margin-top: 7px;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.inst-model {
  margin-top: 3px;
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gantt-right { flex: 1; }
.gantt-right::-webkit-scrollbar { width: 6px; height: 6px; }
.gantt-right::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
.gantt-timeline-header { display: flex; height: 50px; border-bottom: 1px solid #cbd5e1; position: sticky; top: 0; background: #f1f5f9; z-index: 4; }
.gantt-col-header { display: flex; flex-direction: column; align-items: center; justify-content: center; border-right: 1px solid #e2e8f0; font-size: 12px; color: #64748b; flex-shrink: 0; box-sizing: border-box; }
.gantt-col-header.is-weekend { background: #fff7ed; }
.gantt-col-header.is-today { background: #dbeafe; color: #1d4ed8; }
.gantt-col-header.is-current { box-shadow: inset 0 -2px 0 #2563eb; }
.col-label-primary { font-weight: 600; font-size: 13px; }
.col-label-sub { font-size: 10px; color: #94a3b8; }

.gantt-timeline-body { position: relative; background: #fff; }
.gantt-entity-row { position: relative; display: flex; border-bottom: none; }
.gantt-entity-row.is-subrow { border-top: none; border-bottom: none; background: #ffffff; }
.gantt-entity-row.is-last { border-bottom: 1px solid #cbd5e1; }
.gantt-entity-row.is-last .gantt-grid-cell { border-bottom: none; }
.gantt-entity-row.is-subrow:nth-child(even) { background: #fafafa; }
.gantt-entity-row:nth-child(even):not(.is-subrow) { background: #f8fafc; }
.gantt-grid-cell { border-right: 1px solid #e2e8f0; border-bottom: 1px solid #f1f5f9; flex-shrink: 0; box-sizing: border-box; }
.gantt-grid-cell.is-weekend { background: #fff7ed; }
.gantt-grid-cell.is-today { background: #eff6ff; }
.gantt-grid-cell.is-current { background: #dbeafe; }

.gantt-bar {
  position: absolute;
  border-radius: 5px;
  display: flex;
  align-items: center;
  padding: 0 4px;
  cursor: pointer;
  overflow: hidden;
  transition: box-shadow 0.15s, transform 0.15s;
  z-index: 1;
  box-sizing: border-box;
  gap: 2px;
  min-width: 0;
  border-left-width: 4px;
  border-left-style: solid;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}
.gantt-bar:hover { box-shadow: 0 4px 10px rgba(15, 23, 42, 0.14); transform: translateY(-1px); z-index: 3; }
.bar-delay-segment {
  position: absolute;
  top: 3px;
  bottom: 3px;
  z-index: 1;
  border: 1px solid #ef4444;
  border-radius: 4px;
  box-sizing: border-box;
  background:
    repeating-linear-gradient(-45deg, rgba(220, 38, 38, 0.18) 0 4px, rgba(254, 226, 226, 0.7) 4px 8px),
    rgba(254, 242, 242, 0.9);
  pointer-events: none;
}
.bar-delay-segment::after {
  content: "";
  position: absolute;
  right: -1px;
  top: -1px;
  border-top: 10px solid #dc2626;
  border-left: 10px solid transparent;
}
.bar-tag {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.68);
  color: inherit;
}
.bar-status-dot {
  position: absolute;
  right: 2px;
  top: 2px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
}
.bar-label { position: relative; z-index: 2; display: flex; flex-direction: column; justify-content: center; gap: 1px; overflow: hidden; min-width: 0; color: inherit; line-height: 1.05; }
.bar-project, .bar-task { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-project { font-size: 9px; font-weight: 700; }
.bar-task { font-size: 8px; font-weight: 500; opacity: 0.94; }
.gantt-container.is-week-view .gantt-bar { padding: 0 3px; gap: 1px; }
.gantt-container.is-week-view .bar-tag {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  font-size: 7px;
}
.gantt-container.is-week-view .bar-status-dot {
  right: 1px;
  top: 1px;
  width: 3px;
  height: 3px;
}
.gantt-container.is-week-view .bar-label { gap: 0; line-height: 1; }
.gantt-container.is-week-view .bar-project { font-size: 8px; }
.gantt-container.is-week-view .bar-task { font-size: 7px; opacity: 0.96; }
.gantt-bar.is-compact { padding: 0 4px; justify-content: center; }
.gantt-bar.is-compact .bar-label { display: none; }
.gantt-bar.is-compact .bar-tag { width: 16px; height: 16px; font-size: 9px; }
.bar-delay-badge { position: absolute; right: 0; top: 0; z-index: 2; width: 14px; height: 14px; border-radius: 2px; display: flex; align-items: center; justify-content: center; background: #dc2626; color: #fff; font-size: 10px; font-weight: 700; line-height: 1; pointer-events: none; }

/* Status colors */
.status-scheduled {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  border-left-color: #2563eb;
}
.status-running {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
  border-left-color: #10b981;
}
.status-running::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(20, 184, 166, 0.12) 50%, transparent 100%);
  pointer-events: none;
}
.status-completed {
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #cbd5e1;
  border-left-color: #94a3b8;
}
.status-blocked {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
  border-left-color: #dc2626;
}
.gantt-bar.has-delay {
  color: #b91c1c;
  border-color: #fecaca;
  border-left-color: #dc2626;
}
.gantt-bar.status-scheduled,
.gantt-bar.status-running,
.gantt-bar.status-completed,
.gantt-bar.status-blocked {
  border-left-width: 4px;
}
.auto-scroll-note {
  position: absolute;
  right: 16px;
  bottom: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  color: #64748b;
  font-size: 12px;
  z-index: 5;
}

.gantt-tooltip { position: fixed; background: #1e293b; color: #fff; padding: 12px 16px; border-radius: 8px; font-size: 12px; z-index: 1000; pointer-events: none; min-width: 180px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.tooltip-title { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
.tooltip-row { display: flex; justify-content: space-between; padding: 2px 0; }
.tooltip-row span { color: #94a3b8; }
.tooltip-row.is-delay { color: #fecaca; }
</style>
