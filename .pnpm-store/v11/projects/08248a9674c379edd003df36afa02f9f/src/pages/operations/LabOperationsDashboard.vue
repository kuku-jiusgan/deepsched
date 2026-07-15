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
            <em>{{ item.next_project || '未关联项目' }} · {{ item.next_user || '未分配' }}</em>
            <small>{{ formatNextStart(item.next_start) }}</small>
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
                <div><dt>项目编号</dt><dd>{{ selectedInstrument.current_project_code || '-' }}</dd></div>
                <div><dt>当前任务</dt><dd>{{ selectedInstrument.current_task || '未占用' }}</dd></div>
                <div><dt>预计完成</dt><dd>{{ formatExpectedEnd(selectedInstrument.current_task_end) }}</dd></div>
                <div><dt>负责人</dt><dd>{{ selectedInstrument.current_user || '未分配' }}</dd></div>
                <div><dt>下一项目</dt><dd>{{ selectedInstrument.next_project || '暂无待执行项目' }}</dd></div>
                <div><dt>下一项目编号</dt><dd>{{ selectedInstrument.next_project_code || '-' }}</dd></div>
                <div><dt>下一任务</dt><dd>{{ selectedInstrument.next_task || '暂无待执行任务' }}</dd></div>
                <div><dt>下一负责人</dt><dd>{{ selectedInstrument.next_user || '未分配' }}</dd></div>
                <div><dt>预计开始</dt><dd>{{ formatNextStart(selectedInstrument.next_start) }}</dd></div>
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
                    <div><dt>项目编号</dt><dd>{{ item.current_project_code || '-' }}</dd></div>
                    <div><dt>当前任务</dt><dd>{{ item.current_task || '未占用' }}</dd></div>
                    <div><dt>预计完成</dt><dd>{{ formatExpectedEnd(item.current_task_end) }}</dd></div>
                    <div><dt>负责人</dt><dd>{{ item.current_user || '未分配' }}</dd></div>
                    <div><dt>下一项目</dt><dd>{{ item.next_project || '暂无待执行项目' }}</dd></div>
                    <div><dt>下一项目编号</dt><dd>{{ item.next_project_code || '-' }}</dd></div>
                    <div><dt>下一任务</dt><dd>{{ item.next_task || '暂无待执行任务' }}</dd></div>
                    <div><dt>下一负责人</dt><dd>{{ item.next_user || '未分配' }}</dd></div>
                    <div><dt>预计开始</dt><dd>{{ formatNextStart(item.next_start) }}</dd></div>
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
          <div
            v-if="warningTasks.length"
            class="warning-viewport"
            :style="{ '--warning-scroll-duration': warningScrollDuration }"
          >
            <div class="warning-scroll-track" :class="{ 'is-scrolling': isWarningScrollEnabled }">
              <div v-for="copyIndex in warningCopyCount" :key="`warning-copy-${copyIndex}`" class="warning-scroll-copy">
                <div v-for="item in warningTasks" :key="`warning-task-${copyIndex}-${item.id}`" class="warning-task-row">
                  <div class="warning-task-head">
                    <strong>{{ item.project_code || '未关联项目' }}</strong>
                    <em>{{ warningTaskStatus(item) }}</em>
                  </div>
                  <span>{{ item.task_name || '-' }}</span>
                  <small>{{ item.instrument_code || item.instrument_name || '-' }} · {{ item.assignee_name || '未分配' }}</small>
                  <small>{{ warningTaskReason(item) }}</small>
                </div>
              </div>
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
const WARNING_SCROLL_THRESHOLD = 2
const WARNING_SCROLL_SECONDS_PER_ITEM = 6
const WARNING_SCROLL_MIN_SECONDS = 18

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
let isFetching = false

const currentTime = computed(() => now.value.format('YYYY-MM-DD HH:mm:ss'))
const runningInstruments = computed(() => instruments.value.filter(item => statusClass(item) === 'running'))
const idleInstruments = computed(() => instruments.value.filter(item => statusClass(item) === 'idle'))
const warningInstruments = computed(() => instruments.value.filter(item => ['fault', 'maint'].includes(statusClass(item))))
const utilizationByInstrument = computed(() => new Map(utilization.value.map(item => [item.instrument_id, item])))
const warningTasks = computed(() => timeSlots.value
  .filter(isWarningTask)
  .sort((left, right) => warningSortTime(right) - warningSortTime(left)))
const isWarningScrollEnabled = computed(() => warningTasks.value.length > WARNING_SCROLL_THRESHOLD)
const warningCopyCount = computed(() => isWarningScrollEnabled.value ? 2 : 1)
const warningScrollDuration = computed(() => {
  const seconds = Math.max(WARNING_SCROLL_MIN_SECONDS, warningTasks.value.length * WARNING_SCROLL_SECONDS_PER_ITEM)
  return `${seconds}s`
})
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

function formatExpectedEnd(value: string | null | undefined) {
  return value ? dayjs(value).format('MM-DD HH:mm') : '-'
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
  if (isFetching) return
  isFetching = true
  if (!silent) isLoading.value = true
  try {
    const [dashboardData, statusList, utilizationList, baseInstruments, slots] = await Promise.all([
      getDashboard(),
      getLabStatus(),
      getUtilization(),
      getInstruments({ include_unavailable: true }),
      getTimeslots(),
    ])
    const nextInstruments = mergeInstruments(statusList, baseInstruments)
    const hasInstrumentChanges = hasDataChanged(instruments.value, nextInstruments)

    if (hasDataChanged(dashboard.value, dashboardData)) dashboard.value = dashboardData
    if (hasDataChanged(utilization.value, utilizationList)) utilization.value = utilizationList
    if (hasDataChanged(timeSlots.value, slots)) timeSlots.value = slots
    if (hasInstrumentChanges) {
      instruments.value = nextInstruments
      syncSelectedInstrument()
    }
  } catch {
    message.error('实验室运营看板加载失败')
  } finally {
    isFetching = false
    isLoading.value = false
  }
}

function hasDataChanged<T>(current: T, next: T) {
  return JSON.stringify(current) !== JSON.stringify(next)
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

<style scoped src="./LabOperationsDashboard.css"></style>
