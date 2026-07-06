<template>
  <div class="gantt-page" :class="{ 'is-fullscreen': isFullscreen }">
    <div class="page-header"><h2>仪器甘特图</h2></div>

    <div class="action-bar">
      <a-button-group>
        <a-button :type="viewMode === 'day' ? 'primary' : 'default'" @click="switchView('day')">日</a-button>
        <a-button :type="viewMode === 'week' ? 'primary' : 'default'" @click="switchView('week')">周</a-button>
        <a-button :type="viewMode === 'month' ? 'primary' : 'default'" @click="switchView('month')">月</a-button>
      </a-button-group>
      <a-button @click="goPrev"><LeftOutlined /></a-button>
      <span style="font-weight: 600; min-width: 160px; text-align: center">{{ periodLabel }}</span>
      <a-button @click="goNext"><RightOutlined /></a-button>
      <a-button @click="goToday">今天</a-button>
      <a-button @click="fetchData"><ReloadOutlined /> 刷新</a-button>
      <a-button @click="toggleFullscreen"><component :is="isFullscreen ? FullscreenExitOutlined : FullscreenOutlined" /> 全屏</a-button>
      <span style="margin-left: auto; font-size: 12px; color: #94a3b8">{{ slots.length }} 个时间槽</span>
    </div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 80px auto" />

    <div v-else-if="!instruments.length" style="padding: 80px; text-align: center; color: #94a3b8">
      暂无仪器数据，请先在「基础资源台账」中添加仪器并生成排程
    </div>

    <div v-else class="gantt-container" ref="containerRef">
      <div class="gantt-left">
        <div class="gantt-header-cell">仪器</div>
        <div v-for="row in flatRows" :key="'l-' + row.inst.id + '-q' + row.quarter"
          class="gantt-left-row" :class="{ 'is-subrow': row.isSubrow, 'is-last': row.isLast || (viewMode === 'week' && !row.isSubrow) }"
          :style="getLeftRowStyle(row)">
          <template v-if="!row.isSubrow || viewMode !== 'week'">
            <div class="inst-code">{{ row.inst.code }}</div>
            <div class="inst-name">{{ row.inst.name }}</div>
            <div class="inst-model" v-if="row.inst.model">{{ row.inst.model }}</div>
          </template>
        </div>
      </div>

      <div class="gantt-right">
        <div class="gantt-timeline-header" :style="{ width: totalWidth + 'px' }">
          <div v-for="col in timeColumns" :key="col.key" class="gantt-col-header" :style="{ width: colWidth + 'px' }"
            :class="{ 'is-weekend': col.isWeekend, 'is-today': col.isToday }">
            <div class="col-label-primary">{{ col.label }}</div>
            <div v-if="col.subLabel" class="col-label-sub">{{ col.subLabel }}</div>
          </div>
        </div>
        <div class="gantt-timeline-body" :style="{ width: totalWidth + 'px' }">
          <div v-for="row in flatRows" :key="'r-' + row.inst.id + '-q' + row.quarter"
            class="gantt-entity-row" :class="{ 'is-subrow': row.isSubrow, 'is-last': row.isLast || (viewMode === 'week' && !row.isSubrow) }"
            :style="{ height: Math.max(12, rowHeight) + 'px' }">
            <div v-for="col in timeColumns" :key="col.key" class="gantt-grid-cell"
              :style="{ width: colWidth + 'px' }" :class="{ 'is-weekend': col.isWeekend, 'is-today': col.isToday }" />
            <div v-for="slot in getSlotsForQuarter(row.inst.id, row.quarter)" :key="slot.id"
              class="gantt-bar" :class="'status-' + slot.status"
              :style="getBarStyle(slot, row.quarter)"
              @mouseenter="e => showTooltip(slot, e)"
              @mouseleave="hideTooltip">
              <span class="bar-tag">{{ getProcessTag(slot.task_type) }}</span><span class="bar-label">{{ slot.task_name }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="hoveredSlot" class="gantt-tooltip" :style="tooltipStyle">
      <div class="tooltip-title">{{ hoveredSlot.task_name }}</div>
      <div class="tooltip-row"><span>工序</span>{{ getTaskTypeLabel(hoveredSlot.task_type) }}</div>
      <div class="tooltip-row"><span>项目</span>{{ hoveredSlot.project_name }}</div>
      <div class="tooltip-row"><span>负责人</span>{{ hoveredSlot.assignee_name || '-' }}</div>
      <div class="tooltip-row"><span>开始</span>{{ dayjs(hoveredSlot.plan_start).format('MM-DD HH:mm') }}</div>
      <div class="tooltip-row"><span>结束</span>{{ dayjs(hoveredSlot.plan_end).format('MM-DD HH:mm') }}</div>
      <div class="tooltip-row"><span>状态</span>{{ statusLabel(hoveredSlot.status) }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined, ReloadOutlined, FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons-vue'
import { getInstruments, getTimeslots, getTaskTypes, type TaskTypeConfig } from '@/services/api'
import type { Instrument, TimeSlot } from '@/types'
import dayjs from 'dayjs'

const loading = ref(true)
const instruments = ref<Instrument[]>([])
const slots = ref<TimeSlot[]>([])
const viewMode = ref<'day' | 'week' | 'month'>('week')
const cursorDate = ref(dayjs().startOf('week'))
const isFullscreen = ref(false)
const hoveredSlot = ref<TimeSlot | null>(null)
const tooltipX = ref(0)
const tooltipY = ref(0)
const tooltipStyle = computed(() => ({ left: tooltipX.value + 'px', top: tooltipY.value + 'px' }))
const containerRef = ref<HTMLElement | null>(null)
const leftRef = ref<HTMLElement | null>(null)
const rightRef = ref<HTMLElement | null>(null)
const colWidth = ref(140)
const rowHeight = ref(200)
const taskTypeMap = ref<Record<string, string>>({})
const laneMap = ref<Record<number, Record<number, number>>>({})
const laneCounts = ref<Record<number, number>>({})

const flatRows = computed(() => {
  const rows: { inst: Instrument; quarter: number; isSubrow: boolean; isLast: boolean }[] = []
  for (const inst of instruments.value) {
    const qCount = viewMode.value === 'week' ? 4 : 1
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
  key: string; label: string; subLabel: string; isWeekend: boolean; isToday: boolean
  start: dayjs.Dayjs; end: dayjs.Dayjs
}

const timeColumns = computed<TimeCol[]>(() => {
  const cols: TimeCol[] = []
  const today = dayjs().format('YYYY-MM-DD')
  if (viewMode.value === 'day') {
    for (let h = 0; h < 24; h++) {
      const d = cursorDate.value.hour(h)
      cols.push({
        key: 'h' + h, label: String(h).padStart(2, '0') + ':00', subLabel: '', isWeekend: false,
        isToday: d.format('YYYY-MM-DD') === today, start: d, end: d.add(1, 'hour')
      })
    }
  } else if (viewMode.value === 'week') {
    for (let i = 0; i < 7; i++) {
      const d = cursorDate.value.add(i, 'day')
      const dow = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.day()]
      cols.push({
        key: 'd' + i, label: dow, subLabel: d.format('MM/DD'),
        isWeekend: d.day() === 0 || d.day() === 6,
        isToday: d.format('YYYY-MM-DD') === today, start: d.startOf('day'), end: d.endOf('day')
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
        isToday: d.format('YYYY-MM-DD') === today, start: d.startOf('day'), end: d.endOf('day')
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

function getEntityRowStyle(_index: number, _quarter?: number) {
  return { height: Math.max(12, rowHeight.value) + 'px' }
}

function getLeftRowStyle(row: { isSubrow: boolean }) {
  if (viewMode.value === 'week' && !row.isSubrow) {
    return { height: rowHeight.value * 4 + 'px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }
  }
  if (viewMode.value === 'week' && row.isSubrow) {
    return { height: '0', overflow: 'hidden', padding: '0', border: 'none' }
  }
  return { height: Math.max(12, rowHeight.value) + 'px' }
}

function getSlotsForQuarter(instId: number, quarter: number) {
  if (viewMode.value !== 'week') return getSlotsForInstrument(instId)
  const cols = timeColumns.value
  return getSlotsForInstrument(instId).filter(s => {
    const start = dayjs(s.plan_start)
    const end = dayjs(s.plan_end)
    for (const col of cols) {
      const dayStart = col.start
      const qStart = dayStart.hour(quarter * 6)
      const qEnd = dayStart.hour(quarter * 6 + 6)
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

  // In week view with quarters, position within the quarter sub-row
  if (viewMode.value === 'week' && quarter !== undefined) {
    let barStartCol = -1, barEndCol = -1
    for (let i = 0; i < cols.length; i++) {
      const dayStart = cols[i].start
      const qStart = dayStart.hour(quarter * 6)
      const qEnd = dayStart.hour(quarter * 6 + 6)
      if (end.isAfter(qStart) && start.isBefore(qEnd)) {
        if (barStartCol === -1) barStartCol = i
        barEndCol = i
      }
    }
    if (barStartCol === -1) return { display: 'none' }
    const firstDayStart = cols[barStartCol].start
    const firstQStart = firstDayStart.hour(quarter * 6)
    const firstQEnd = firstDayStart.hour(quarter * 6 + 6)
    const clampedStart = start.isBefore(firstQStart) ? firstQStart : start
    const firstOffset = clampedStart.diff(firstQStart, 'second', true) / 21600
    const lastDayStart = cols[barEndCol].start
    const lastQStart = lastDayStart.hour(quarter * 6)
    const lastQEnd = lastDayStart.hour(quarter * 6 + 6)
    const clampedEnd = end.isAfter(lastQEnd) ? lastQEnd : end
    const lastOffset = clampedEnd.diff(lastQStart, 'second', true) / 21600
    const barLeft = (barStartCol + firstOffset) * cw
    const barRight = (barEndCol + lastOffset) * cw
    return {
      left: barLeft + 'px',
      width: Math.max(3, barRight - barLeft) + 'px',
      top: '2px', bottom: '2px'
    }
  }
  
  const lane = (laneMap.value[slot.instrument_id] || {})[slot.id] || 0
  const laneCount = laneCounts.value[slot.instrument_id] || 1
  const laneH = Math.max(26, Math.floor((rowHeight.value - 4) / laneCount))
  const top = lane * laneH + 2

  return { left: left + 'px', width: Math.max(3, right - left) + 'px', top: top + 'px', height: (laneH - 2) + 'px' }
}

const processTags: Record<string, string> = {
  FFKF_001: '开',   // 方法开发
  QCFA_001: '案',   // 起草方案
  FFYZ_001: '验',   // 方法验证
  SJCL_001: '数',   // 数据处理
  ZXBG_001: '报',   // 撰写报告
}
function getProcessTag(code: string | undefined) { return code ? (processTags[code] || code.charAt(0)) : '' }
function getTaskTypeLabel(code: string | undefined) { return code ? (taskTypeMap.value[code] || code) : '' }

function statusLabel(s: string) {
  const m: Record<string, string> = { scheduled: '待处理', pending: '待处理', running: '运行中', completed: '已完成', blocked: '已延期', interrupted: '已延期' }
  return m[s] || s
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
  if (viewMode.value !== 'day' || !rightRef.value) return
  nextTick(() => {
    const hour = dayjs().hour()
    const containerH = containerRef.value.clientHeight
    rightRef.value.scrollTop = Math.max(0, hour * (rowHeight.value / 24) - containerH / 2)
  })
}

function recalc() {
  nextTick(() => {
    setTimeout(() => {
      if (!containerRef.value || containerRef.value.clientHeight <= 0) return
      computeLanes()
      const headerH = 50
      const availableH = containerRef.value.clientHeight - headerH - 2
      const entityCount = Math.max(1, instruments.value.length)
      const perEntity = Math.floor(availableH / entityCount)
      if (viewMode.value === 'week') {
        rowHeight.value = Math.floor(perEntity / 4)
      } else {
        rowHeight.value = perEntity
      }
      const available = containerRef.value.clientWidth - 180 - 2
      const cols = viewMode.value === 'day' ? 24 : viewMode.value === 'week' ? 7 : cursorDate.value.daysInMonth()
      colWidth.value = Math.max(60, available / cols)
    }, 50)
  })
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
    if (isFullscreen.value) { stopAutoScroll(); startAutoScroll() }
  }
}

let resizeObserver: ResizeObserver | null = null

let refreshTimer: ReturnType<typeof setInterval> | null = null


let autoScrollTimer: ReturnType<typeof setInterval> | null = null
let isAutoScrolling = false

function toggleFullscreen() {
  if (!isFullscreen.value) {
    document.documentElement.requestFullscreen()
    isFullscreen.value = true
  } else {
    stopAutoScroll()
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

function startAutoScroll() {
  if (!containerRef.value) return
  const maxScroll = containerRef.value.scrollHeight - containerRef.value.clientHeight
  if (maxScroll <= 0) {
    setTimeout(() => { startAutoScroll() }, 300)
    return
  }
  stopAutoScroll()
  isAutoScrolling = true
  let direction = 1
  autoScrollTimer = setInterval(() => {
    if (!containerRef.value) { stopAutoScroll(); return }
    const current = containerRef.value.scrollTop
    if (current >= maxScroll - 2) direction = -1
    if (current <= 2) direction = 1
    containerRef.value.scrollTop += direction * 0.6
  }, 20)
}

function stopAutoScroll() {
  isAutoScrolling = false
  if (autoScrollTimer) {
    clearInterval(autoScrollTimer)
    autoScrollTimer = null
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  if (isFullscreen.value) {
    setTimeout(() => { startAutoScroll() }, 500)
  } else {
    stopAutoScroll()
  }
}

onMounted(() => {
  fetchData()
  refreshTimer = setInterval(() => fetchData(true), 30000)
  window.addEventListener('resize', recalc)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  nextTick(() => {
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(() => {
        if (containerRef.value && containerRef.value.clientHeight > 0) {
          recalc()
        }
      })
      resizeObserver.observe(containerRef.value)
    }
  })
})
onUnmounted(() => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  window.removeEventListener('resize', recalc)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  stopAutoScroll()
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
})
</script>

<style scoped>
.gantt-page { display: flex; flex-direction: column; height: calc(100vh - 64px); }

.gantt-page.is-fullscreen {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 9999;
  background: #f7f8fa; padding: 16px; height: 100vh;
}
.gantt-page.is-fullscreen .gantt-container { flex: 1; min-height: 0; }
.gantt-page.is-fullscreen .page-header { display: none; }
.gantt-page.is-fullscreen .action-bar { padding: 0 0 12px 0; }

.gantt-container { display: flex; flex: 1; border: 1px solid #e5e7eb; border-radius: 8px; overflow: auto; margin-top: 12px; min-height: 0; }

.gantt-left { width: 180px; min-width: 180px; background: #f8fafc; border-right: 1px solid #e5e7eb; position: sticky; left: 0; z-index: 3; }
.gantt-left::-webkit-scrollbar { width: 0; }
.gantt-header-cell { height: 50px; display: flex; align-items: center; padding: 0 12px; font-weight: 600; font-size: 13px; color: #475569; border-bottom: 2px solid #c0c7cf; background: #f1f5f9; }
.gantt-left-row { display: flex; flex-direction: column; justify-content: center; padding: 0 12px; border-bottom: none; overflow: hidden; }
.gantt-left-row.is-last { border-bottom: 2px solid #b0bec5; }
.inst-code { font-size: 12px; font-weight: 700; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.inst-name { font-size: 12px; font-weight: 400; color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.inst-model { font-size: 10px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.gantt-right { flex: 1; }
.gantt-right::-webkit-scrollbar { width: 6px; height: 6px; }
.gantt-right::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
.gantt-timeline-header { display: flex; height: 50px; border-bottom: 2px solid #c0c7cf; position: sticky; top: 0; background: #f1f5f9; z-index: 4; }
.gantt-col-header { display: flex; flex-direction: column; align-items: center; justify-content: center; border-right: 1px solid #c0c7cf; font-size: 12px; color: #64748b; flex-shrink: 0; box-sizing: border-box; }
.gantt-col-header.is-weekend { background: #fef2f2; }
.gantt-col-header.is-today { background: #dbeafe; }
.col-label-primary { font-weight: 600; font-size: 13px; }
.col-label-sub { font-size: 10px; color: #94a3b8; }

.gantt-timeline-body { position: relative; background: #fff; }
.gantt-entity-row { position: relative; display: flex; border-bottom: none; }
.gantt-entity-row.is-subrow { border-top: none; border-bottom: none; background: #fdfdfe; }
.gantt-entity-row.is-last { border-bottom: 2px solid #b0bec5; }
.gantt-entity-row.is-last .gantt-grid-cell { border-bottom: none; }
.gantt-entity-row.is-subrow:nth-child(even) { background: #f5f6f8; }
.gantt-entity-row:nth-child(even):not(.is-subrow) { background: #f8fafc; }
.gantt-grid-cell { border-right: 1px solid #c0c7cf; border-bottom: 1px solid #c0c7cf; flex-shrink: 0; box-sizing: border-box; }
.gantt-grid-cell.is-weekend { background: #fef2f2; }
.gantt-grid-cell.is-today { background: #eff6ff; }

.gantt-bar { position: absolute; border-radius: 3px; display: flex; align-items: center; padding: 0 5px; cursor: pointer; overflow: hidden; transition: box-shadow 0.15s; z-index: 1; box-sizing: border-box; gap: 3px; min-width: 0; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
.gantt-bar:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.15); z-index: 3; }
.bar-tag { flex-shrink: 0; width: 18px; height: 18px; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; background: rgba(0,0,0,0.12); color: inherit; }
.bar-label { font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; min-width: 0; color: inherit; }

/* Status colors */
.status-scheduled, .status-pending {
  background: #FF9800; color: #FFFFFF; border: 1px solid #F57C00;
  box-shadow: 0 2px 6px rgba(255, 152, 0, 0.3);
}
.status-running {
  background: #4CAF50; color: #FFFFFF; border: 1px solid #388E3C;
  box-shadow: 0 2px 6px rgba(76, 175, 80, 0.3);
}
.status-running::after {
  content: ""; position: absolute; left: 100%; top: 0; bottom: 0;
  width: 20px; background: #E8F5E9; border-radius: 0 3px 3px 0;
  pointer-events: none;
}
.status-completed {
  background: #2196F3; color: #FFFFFF; border: 1px solid #1976D2;
  box-shadow: 0 2px 6px rgba(33, 150, 243, 0.3);
}
.status-blocked, .status-interrupted {
  background: #E53935; color: #FFFFFF; border: 1px solid #C62828;
  box-shadow: 0 2px 6px rgba(229, 57, 53, 0.3);
}

.gantt-tooltip { position: fixed; background: #1e293b; color: #fff; padding: 12px 16px; border-radius: 8px; font-size: 12px; z-index: 1000; pointer-events: none; min-width: 180px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.tooltip-title { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
.tooltip-row { display: flex; justify-content: space-between; padding: 2px 0; }
.tooltip-row span { color: #94a3b8; }
</style>