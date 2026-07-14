<template>
  <div class="lab-ops-screen">
    <header class="screen-header">
      <div>
        <h2>实验室运营看板</h2>
      </div>
      <div class="screen-clock">
        <strong>{{ currentTime }}</strong>
      </div>
    </header>

    <section class="kpi-strip" aria-label="实验室运营指标">
      <div v-for="item in kpiItems" :key="item.label" class="kpi-item" :class="item.tone">
        <component :is="item.icon" />
        <div>
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </div>
      </div>
    </section>
    <main class="screen-main">
      <section class="instrument-grid" aria-label="仪器运行阵列">
        <a-empty v-if="!isLoading && !instruments.length" description="暂无可用仪器" />
        <button
          v-for="item in instruments"
          :key="item.id"
          class="instrument-card"
          :class="[statusClass(item), { selected: selectedInstrument?.id === item.id }]"
          type="button"
          @click="selectInstrument(item)"
        >
          <div class="card-topline">
            <span class="instrument-code">{{ item.code }}</span>
            <span class="status-pill">{{ statusText(item) }}</span>
          </div>
          <div class="instrument-title">
            <strong>{{ item.name }}</strong>
            <span>{{ specText(item) }}</span>
          </div>
          <div v-if="item.current_task" class="task-block">
            <span>当前任务</span>
            <strong>{{ item.current_task }}</strong>
            <em>{{ item.current_project || '未关联项目' }} · {{ item.current_user || '未分配' }}</em>
            <a-progress
              :percent="Math.round(item.progress || 0)"
              :show-info="false"
              size="small"
              :stroke-color="progressColor(item)"
            />
          </div>
          <div v-else class="task-block is-idle">
            <span>下一任务</span>
            <strong>{{ item.next_task || '暂无待执行任务' }}</strong>
            <em>{{ formatNextStart(item.next_start) }}</em>
            <div class="progress-placeholder"></div>
          </div>
        </button>
      </section>

      <aside class="side-panel">
        <section class="panel-card selected-card">
          <div class="detail-viewport" :style="{ '--detail-scroll-duration': detailScrollDuration }">
            <div
              v-if="isDetailPinned && selectedInstrument"
              class="selected-detail selected is-pinned"
              @click="releasePinnedDetail"
            >
              <div class="selected-head">
                <span class="detail-dot" :class="statusClass(selectedInstrument)"></span>
                <div>
                  <strong>{{ selectedInstrument.code }}</strong>
                  <span>{{ selectedInstrument.name }}</span>
                </div>
              </div>
              <dl class="detail-list">
                <div><dt>品牌型号</dt><dd>{{ specText(selectedInstrument) }}</dd></div>
                <div><dt>位置分组</dt><dd>{{ selectedInstrument.location || '-' }} · {{ groupText(selectedInstrument.group) }}</dd></div>
                <div><dt>当前项目</dt><dd>{{ selectedInstrument.current_project || '暂无运行项目' }}</dd></div>
                <div><dt>当前任务</dt><dd>{{ selectedInstrument.current_task || '未占用' }}</dd></div>
                <div><dt>负责人</dt><dd>{{ selectedInstrument.current_user || '未分配' }}</dd></div>
                <div><dt>下一任务</dt><dd>{{ selectedInstrument.next_task || '暂无待执行任务' }}</dd></div>
                <div><dt>仪器利用率</dt><dd>{{ utilizationText(selectedInstrument.id) }}</dd></div>
              </dl>
            </div>
            <div v-else-if="instruments.length" class="detail-scroll-track">
              <div v-for="copyIndex in 2" :key="`detail-copy-${copyIndex}`" class="detail-scroll-copy">
                <div
                  v-for="item in instruments"
                  :key="`detail-${copyIndex}-${item.id}`"
                  class="selected-detail"
                  :class="{ selected: selectedInstrument?.id === item.id }"
                  @click="selectInstrument(item)"
                >
                  <div class="selected-head">
                    <span class="detail-dot" :class="statusClass(item)"></span>
                    <div>
                      <strong>{{ item.code }}</strong>
                      <span>{{ item.name }}</span>
                    </div>
                  </div>
                  <dl class="detail-list">
                    <div><dt>品牌型号</dt><dd>{{ specText(item) }}</dd></div>
                    <div><dt>位置分组</dt><dd>{{ item.location || '-' }} · {{ groupText(item.group) }}</dd></div>
                    <div><dt>当前项目</dt><dd>{{ item.current_project || '暂无运行项目' }}</dd></div>
                    <div><dt>当前任务</dt><dd>{{ item.current_task || '未占用' }}</dd></div>
                    <div><dt>负责人</dt><dd>{{ item.current_user || '未分配' }}</dd></div>
                    <div><dt>下一任务</dt><dd>{{ item.next_task || '暂无待执行任务' }}</dd></div>
                    <div><dt>仪器利用率</dt><dd>{{ utilizationText(item.id) }}</dd></div>
                  </dl>
                </div>
              </div>
            </div>
            <a-empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" description="暂无仪器" />
          </div>
        </section>

        <section class="panel-card">
          <div class="panel-title">
            <span>延期预警</span>
            <em v-if="warningTasks.length">{{ warningTasks.length }} 项</em>
          </div>
          <div v-if="warningTasks.length" class="compact-list">
            <div v-for="item in warningTasks.slice(0, WARNING_TASK_DISPLAY_LIMIT)" :key="`warning-task-${item.id}`" class="warning-task-row">
              <div class="warning-task-head">
                <strong>{{ item.project_code || '未关联项目' }}</strong>
                <em>{{ warningTaskStatus(item) }}</em>
              </div>
              <span>{{ item.task_name || '-' }}</span>
              <small>{{ item.instrument_code || item.instrument_name || '-' }} · {{ item.assignee_name || '未分配' }}</small>
              <small>{{ warningTaskReason(item) }}</small>
            </div>
          </div>
          <a-empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" description="暂无延期预警" />
        </section>

      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Empty, message } from 'ant-design-vue'
import {
  AlertOutlined,
  ApiOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FieldTimeOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import {
  getDashboard,
  getInstruments,
  getLabStatus,
  getTimeslots,
  getUtilization,
  type LabStatusInstrument,
} from '@/services/api'
import type { DashboardData, Instrument, TimeSlot, UtilizationStats } from '@/types'

type StatusClass = 'running' | 'idle' | 'fault' | 'maint'

interface DashboardInstrument extends LabStatusInstrument {
  brand?: string | null
  model?: string | null
  availability_status?: string
  instrument_group?: string
}

const REFRESH_INTERVAL_MS = 30_000
const CLOCK_INTERVAL_MS = 1_000
const DETAIL_SCROLL_SECONDS_PER_ITEM = 9
const DETAIL_SCROLL_MIN_SECONDS = 42
const DETAIL_PIN_DURATION_MS = 6_000
const WARNING_TASK_DISPLAY_LIMIT = 2

const dashboard = ref<DashboardData | null>(null)
const instruments = ref<DashboardInstrument[]>([])
const utilization = ref<UtilizationStats[]>([])
const timeSlots = ref<TimeSlot[]>([])
const selectedInstrument = ref<DashboardInstrument | null>(null)
const selectedInstrumentIndex = ref(0)
const isDetailPinned = ref(false)
const isLoading = ref(true)
const now = ref(dayjs())
let refreshTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null
let detailPinTimer: ReturnType<typeof setTimeout> | null = null

const currentTime = computed(() => now.value.format('YYYY-MM-DD HH:mm:ss'))
const runningInstruments = computed(() => instruments.value.filter(item => statusClass(item) === 'running'))
const idleInstruments = computed(() => instruments.value.filter(item => statusClass(item) === 'idle'))
const warningInstruments = computed(() => instruments.value.filter(item => ['fault', 'maint'].includes(statusClass(item))))
const utilizationByInstrument = computed(() => new Map(utilization.value.map(item => [item.instrument_id, item])))
const warningTasks = computed(() => timeSlots.value
  .filter(isWarningTask)
  .sort((left, right) => warningSortTime(right) - warningSortTime(left)))
const detailScrollDuration = computed(() => {
  const seconds = Math.max(DETAIL_SCROLL_MIN_SECONDS, instruments.value.length * DETAIL_SCROLL_SECONDS_PER_ITEM)
  return `${seconds}s`
})

const kpiItems = computed(() => [
  {
    label: '仪器总数',
    value: dashboard.value?.total_instruments || instruments.value.length,
    icon: ExperimentOutlined,
    tone: 'total',
  },
  { label: '运行中', value: runningInstruments.value.length, icon: ThunderboltOutlined, tone: 'running' },
  { label: '空闲仪器', value: idleInstruments.value.length, icon: ApiOutlined, tone: 'idle' },
  { label: '维护/故障', value: warningInstruments.value.length, icon: AlertOutlined, tone: 'warning' },
  { label: '平均利用率', value: `${dashboard.value?.avg_utilization || 0}%`, icon: DashboardOutlined, tone: 'total' },
  { label: '延期任务', value: dashboard.value?.delayed_tasks || 0, icon: FieldTimeOutlined, tone: dashboard.value?.delayed_tasks ? 'danger' : 'total' },
])

function statusClass(instrument: DashboardInstrument): StatusClass {
  if (instrument.status === 'fault') return 'fault'
  if (instrument.status === 'maintenance') return 'maint'
  if (instrument.current_task) return 'running'
  return 'idle'
}

function statusText(instrument: DashboardInstrument) {
  const status = statusClass(instrument)
  if (status === 'running') return '运行中'
  if (status === 'fault') return '故障停机'
  if (status === 'maint') return '维护中'
  return '空闲'
}

function groupText(group: string) {
  if (group === 'GTI_Group') return '基因毒组'
  if (group === 'Quality_Group') return '质量组'
  return group || '未分组'
}

function specText(instrument: DashboardInstrument) {
  return instrument.model || '未填写型号'
}

function progressColor(instrument: DashboardInstrument) {
  const status = statusClass(instrument)
  if (status === 'fault') return '#dc2626'
  if (status === 'maint') return '#ea580c'
  return '#16a34a'
}

function formatNextStart(value: string | null) {
  return value ? dayjs(value).format('MM-DD HH:mm') : '暂无预计开始时间'
}

function clampRate(value: number) {
  return Math.max(0, Math.min(100, Number(value) || 0))
}

function rateText(value: number) {
  return `${clampRate(value)}%`
}

function utilizationText(instrumentId: number) {
  const item = utilizationByInstrument.value.get(instrumentId)
  return item ? rateText(item.actual_utilization_rate) : '暂无统计'
}

function isWarningTask(slot: TimeSlot) {
  return Boolean(slot.delay_reason)
    || Boolean(slot.delay_hours && slot.delay_hours > 0)
    || ['blocked', 'interrupted'].includes(slot.status)
}

function warningSortTime(slot: TimeSlot) {
  return dayjs(slot.delay_reported_at || slot.plan_end || slot.plan_start).valueOf()
}

function warningTaskStatus(slot: TimeSlot) {
  if (slot.status === 'interrupted') return '已中断'
  if (slot.status === 'blocked') return '已阻塞'
  if (slot.delay_hours && slot.delay_hours > 0) return `延期 ${slot.delay_hours}h`
  return '延期'
}

function warningTaskReason(slot: TimeSlot) {
  return slot.delay_reason || formatSlotRange(slot)
}

function formatSlotRange(slot: TimeSlot) {
  return `${dayjs(slot.plan_start).format('MM-DD HH:mm')} - ${dayjs(slot.plan_end).format('MM-DD HH:mm')}`
}

function selectInstrument(instrument: DashboardInstrument) {
  selectedInstrument.value = instrument
  selectedInstrumentIndex.value = Math.max(0, instruments.value.findIndex(item => item.id === instrument.id))
  pinDetailTemporarily()
}

function pinDetailTemporarily() {
  isDetailPinned.value = true
  if (detailPinTimer) clearTimeout(detailPinTimer)
  detailPinTimer = setTimeout(() => {
    isDetailPinned.value = false
    detailPinTimer = null
  }, DETAIL_PIN_DURATION_MS)
}

function releasePinnedDetail() {
  isDetailPinned.value = false
  if (detailPinTimer) {
    clearTimeout(detailPinTimer)
    detailPinTimer = null
  }
}

function mergeInstruments(statusList: LabStatusInstrument[], baseList: Instrument[]): DashboardInstrument[] {
  const baseMap = new Map(baseList.map(item => [item.id, item]))
  return statusList.map(item => {
    const base = baseMap.get(item.id)
    return {
      ...item,
      brand: base?.brand || null,
      model: base?.model || null,
      availability_status: base?.availability_status,
      instrument_group: base?.instrument_group,
    }
  })
}

async function fetchData(silent = true) {
  if (!silent) isLoading.value = true
  try {
    const [dashboardData, statusList, utilizationList, baseInstruments, slots] = await Promise.all([
      getDashboard(),
      getLabStatus(),
      getUtilization(),
      getInstruments({ include_unavailable: true }),
      getTimeslots(),
    ])
    dashboard.value = dashboardData
    utilization.value = utilizationList
    timeSlots.value = slots
    instruments.value = mergeInstruments(statusList, baseInstruments)
    syncSelectedInstrument()
  } catch {
    message.error('实验室运营看板加载失败')
  } finally {
    isLoading.value = false
  }
}

function syncSelectedInstrument() {
  if (!instruments.value.length) {
    selectedInstrument.value = null
    selectedInstrumentIndex.value = 0
    return
  }
  const currentIndex = selectedInstrument.value
    ? instruments.value.findIndex(item => item.id === selectedInstrument.value?.id)
    : selectedInstrumentIndex.value
  selectedInstrumentIndex.value = currentIndex >= 0
    ? currentIndex
    : Math.min(selectedInstrumentIndex.value, instruments.value.length - 1)
  selectedInstrument.value = instruments.value[selectedInstrumentIndex.value]
}

onMounted(() => {
  fetchData(false)
  refreshTimer = setInterval(() => fetchData(true), REFRESH_INTERVAL_MS)
  clockTimer = setInterval(() => {
    now.value = dayjs()
  }, CLOCK_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (clockTimer) clearInterval(clockTimer)
  if (detailPinTimer) clearTimeout(detailPinTimer)
})
</script>

<style scoped>
.lab-ops-screen {
  box-sizing: border-box;
  min-height: calc(100vh - 40px);
  margin: -24px;
  padding: 20px;
  display: grid;
  grid-template-rows: auto;
  gap: 12px;
  background: #eef4fb;
  color: #1e293b;
}

.screen-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding-right: 230px;
}

.screen-header h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
}

.screen-clock {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  color: #64748b;
  font-size: 12px;
}

.screen-clock strong {
  color: #1e293b;
  font-family: var(--font-mono);
  font-size: 17px;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(132px, 1fr));
  gap: 10px;
}

.kpi-item {
  min-height: 72px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 11px;
  border: 1px solid #dbe7f3;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
}

.kpi-item > .anticon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 17px;
}

.kpi-item strong {
  display: block;
  color: #0f172a;
  font-size: 22px;
  line-height: 1.05;
}

.kpi-item span {
  display: block;
  font-size: 12px;
}

.kpi-item span { margin-top: 4px; color: #475569; }
.kpi-item.running > .anticon { color: #16a34a; background: #f0fdf4; }
.kpi-item.idle > .anticon { color: #2563eb; background: #eff6ff; }
.kpi-item.warning > .anticon { color: #ea580c; background: #fff7ed; }
.kpi-item.danger > .anticon { color: #dc2626; background: #fef2f2; }

.screen-main {
  --instrument-row-height: 212px;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 12px;
}

.instrument-grid {
  min-height: 0;
  overflow: visible;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: var(--instrument-row-height);
  align-content: start;
  gap: 12px;
}

.instrument-card {
  min-height: 0;
  height: 100%;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  border: 1px solid #dbe7f3;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.instrument-card:hover,
.instrument-card.selected {
  border-color: #93c5fd;
  box-shadow: 0 3px 8px rgba(37, 99, 235, 0.12);
  transform: translateY(-1px);
}

.card-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.instrument-code {
  max-width: 152px;
  overflow: hidden;
  color: #2563eb;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  padding: 2px 7px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 650;
}

.instrument-card.running .status-pill { background: #f0fdf4; color: #15803d; }
.instrument-card.fault .status-pill { background: #fef2f2; color: #b91c1c; }
.instrument-card.maint .status-pill { background: #fff7ed; color: #c2410c; }

.instrument-title strong,
.instrument-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.instrument-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.instrument-title strong {
  min-width: 0;
  color: #1e293b;
  font-size: 15px;
  flex: 1;
}

.instrument-title span {
  flex: 0 1 auto;
  max-width: 46%;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 11px;
}

.task-block {
  margin-top: auto;
  width: 100%;
  align-self: stretch;
  height: 108px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  border-radius: 7px;
  background: #f8fafc;
}

.task-block span,
.task-block strong,
.task-block em {
  display: block;
}

.task-block span {
  color: #94a3b8;
  font-size: 11px;
  line-height: 16px;
}

.task-block strong {
  margin-top: 3px;
  color: #1e293b;
  font-size: 13px;
  line-height: 18px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-block em {
  margin: 2px 0 8px;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  line-height: 17px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-block :deep(.ant-progress) {
  margin-top: auto;
  line-height: 1;
}

.progress-placeholder {
  height: 8px;
  margin-top: auto;
  border-radius: 999px;
  background: transparent;
}

.task-block.is-idle { background: #eff6ff; }

.side-panel {
  min-height: 0;
  overflow: visible;
  display: grid;
  grid-template-rows:
    calc(var(--instrument-row-height) * 2 + 12px)
    var(--instrument-row-height);
  gap: 12px;
  align-content: start;
}

.panel-card {
  min-height: 0;
  height: 100%;
  padding: 13px;
  overflow: hidden;
  border: 1px solid #dbe7f3;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
}

.panel-title {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #1e293b;
  font-size: 13px;
  font-weight: 750;
}

.panel-title em {
  color: #b91c1c;
  font-size: 11px;
  font-style: normal;
  font-weight: 650;
}

.detail-viewport {
  position: relative;
  height: 100%;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 18px, #000 calc(100% - 18px), transparent 100%);
  mask-image: linear-gradient(to bottom, transparent 0, #000 18px, #000 calc(100% - 18px), transparent 100%);
}

.detail-scroll-track {
  animation: detail-scroll var(--detail-scroll-duration, 54s) linear infinite;
  will-change: transform;
}

.detail-scroll-copy {
  display: grid;
  gap: 12px;
  padding-bottom: 12px;
}

.detail-viewport:hover .detail-scroll-track {
  animation-play-state: paused;
}

.selected-detail {
  min-height: var(--instrument-row-height);
  padding: 8px 2px 12px;
  cursor: pointer;
}

.selected-detail.is-pinned {
  min-height: 100%;
}

.selected-detail.selected {
  border-radius: 7px;
  background: #f8fafc;
}

.selected-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 10px;
}

.selected-head strong,
.selected-head span {
  display: block;
}

.selected-head strong {
  color: #2563eb;
  font-family: var(--font-mono);
  font-size: 13px;
}

.selected-head span {
  color: #475569;
  font-size: 12px;
}

.detail-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2563eb;
}

.detail-dot.running { background: #16a34a; }
.detail-dot.fault { background: #dc2626; }
.detail-dot.maint { background: #ea580c; }

.detail-list {
  display: grid;
  gap: 8px;
  margin: 0;
}

.detail-list div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
}

.detail-list dt {
  color: #94a3b8;
  font-size: 12px;
}

.detail-list dd {
  margin: 0;
  color: #334155;
  font-size: 12px;
  overflow-wrap: anywhere;
}

@keyframes detail-scroll {
  from {
    transform: translateY(0);
  }

  to {
    transform: translateY(-50%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .detail-scroll-track {
    animation: none;
  }
}

.compact-list {
  display: grid;
  gap: 7px;
}

.compact-row {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 7px 8px;
  border-radius: 6px;
  background: #f8fafc;
}

.compact-row strong {
  color: #2563eb;
  font-family: var(--font-mono);
  font-size: 11px;
}

.compact-row span {
  overflow: hidden;
  color: #334155;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-row em {
  color: #64748b;
  font-size: 11px;
  font-style: normal;
}

.compact-row.is-warning strong,
.compact-row.is-warning em {
  color: #dc2626;
}

.warning-task-row {
  display: grid;
  gap: 3px;
  padding: 8px;
  border-radius: 6px;
  background: #fef2f2;
}

.warning-task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.warning-task-head strong {
  overflow: hidden;
  color: #b91c1c;
  font-family: var(--font-mono);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.warning-task-head em {
  flex-shrink: 0;
  color: #dc2626;
  font-size: 11px;
  font-style: normal;
  font-weight: 650;
}

.warning-task-row span,
.warning-task-row small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.warning-task-row span {
  color: #1e293b;
  font-size: 12px;
  font-weight: 650;
}

.warning-task-row small {
  color: #64748b;
  font-size: 11px;
}

@media (max-width: 1180px) {
  .kpi-strip { grid-template-columns: repeat(3, 1fr); }
  .screen-main { grid-template-columns: 1fr; }
  .side-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: 320px;
  }
}

@media (max-width: 820px) {
  .lab-ops-screen {
    height: auto;
    min-height: calc(100vh - 88px);
    margin: -16px;
    padding: 12px;
    overflow: visible;
  }
  .screen-header { flex-direction: column; padding-right: 0; }
  .screen-clock { align-items: flex-start; }
  .kpi-strip,
  .side-panel { grid-template-columns: 1fr; }
  .side-panel {
    grid-template-rows:
      calc(var(--instrument-row-height) * 2 + 12px)
      var(--instrument-row-height);
  }
  .instrument-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 620px) {
  .instrument-grid { grid-template-columns: 1fr; }
}
</style>
