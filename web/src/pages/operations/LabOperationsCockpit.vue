<template>
  <div class="cockpit-page">
    <header class="cockpit-header">
      <div class="brand-lockup">
        <span class="brand-mark"><ExperimentOutlined /></span>
        <h1>实验室运营驾驶舱</h1>
      </div>
      <div class="header-meta">
        <span class="date-time"><CalendarOutlined />{{ now.format('YYYY-MM-DD') }}<strong>{{ now.format('HH:mm:ss') }}</strong></span>
        <span class="header-divider"></span>
        <a-dropdown placement="bottomRight">
          <button class="user-menu" type="button"><UserOutlined />{{ currentUserLabel }}<DownOutlined /></button>
          <template #overlay>
            <a-menu @click="handleUserMenu">
              <a-menu-item key="home">进入首页2</a-menu-item>
              <a-menu-item key="logout">退出登录</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </header>

    <main class="cockpit-shell" :class="{ 'is-loading': isLoading }">
      <section class="kpi-grid" aria-label="核心运营指标">
        <article v-for="item in kpis" :key="item.label" class="kpi-card">
          <span class="kpi-icon" :class="item.tone"><component :is="item.icon" /></span>
          <div><span>{{ item.label }}</span><strong>{{ item.value }}<small>{{ item.unit }}</small></strong></div>
        </article>
      </section>

      <section class="overview-grid">
        <article class="instrument-panel panel-frame">
          <h2>{{ instruments.length }}台仪器模型阵列</h2>
          <div v-if="instruments.length" class="instrument-grid">
            <article
              v-for="item in instruments"
              :key="item.id"
              class="instrument-card"
              :class="instrumentCardClass(item.code)"
            >
              <div class="instrument-heading">
                <div><span>{{ item.code }}</span><strong>{{ item.name }}</strong><small>{{ item.model || '型号未设置' }}</small></div>
                <em :class="statusClass(item)">{{ statusText(item) }}</em>
              </div>
              <div class="instrument-picture" :class="instrumentPhotoClass(item.code)">
                <img
                  :src="instrumentImage(item.code)"
                  :alt="`${item.name} ${item.model || ''}`"
                  decoding="async"
                />
              </div>
              <div class="utilization-row">
                <span>利用率</span><i><b :style="{ width: `${utilizationRate(item.id)}%` }"></b></i><strong>{{ utilizationRate(item.id) }}%</strong>
              </div>
            </article>
          </div>
          <a-empty v-else description="暂无可用仪器" />
        </article>

        <aside class="summary-column">
          <section class="summary-card status-summary">
            <h2>设备运行总览</h2>
            <div v-for="item in statusOverview" :key="item.label" class="status-row">
              <span class="summary-icon" :class="item.tone"><component :is="item.icon" /></span>
              <span>{{ item.label }}</span><strong>{{ item.value }}<small>{{ item.unit }}</small></strong><em>{{ item.note }}</em>
            </div>
          </section>
          <section class="summary-card ranking-card">
            <h2>利用率 TOP3</h2>
            <ol>
              <li v-for="(item, index) in topInstruments" :key="item.instrument_id">
                <span :class="`rank-${index + 1}`">{{ index + 1 }}</span>
                <p>{{ item.instrument_name }}<small v-if="instrumentModel(item.instrument_id)">（{{ instrumentModel(item.instrument_id) }}）</small></p>
                <strong>{{ roundedRate(item.actual_utilization_rate) }}%</strong>
              </li>
            </ol>
            <div class="health-state" :class="{ warning: hasWarning }">
              <SafetyCertificateOutlined />
              <div><strong>{{ hasWarning ? '系统存在待处理事项' : '系统运行正常' }}</strong><span>{{ healthDescription }}</span></div>
            </div>
          </section>
        </aside>
      </section>

      <section class="chart-grid">
        <article class="chart-card trend-card">
          <header><h2>本周利用率趋势</h2><span><i></i>平均利用率（%）</span></header>
          <div class="line-chart">
            <div class="y-labels"><span>100</span><span>50</span><span>0</span></div>
            <svg viewBox="0 0 620 120" preserveAspectRatio="none" aria-label="近七日平均利用率折线图">
              <line v-for="y in [14, 57, 100]" :key="y" x1="0" :y1="y" x2="620" :y2="y" />
              <path :d="trendAreaPath" class="trend-area" />
              <polyline :points="trendPoints" />
              <g v-for="(item, index) in weeklyTrend" :key="item.date">
                <circle :cx="trendX(index)" :cy="trendY(item.value)" r="4" />
                <text :x="trendX(index)" :y="trendY(item.value) - 10">{{ item.value }}%</text>
              </g>
            </svg>
            <div class="x-labels"><span v-for="item in weeklyTrend" :key="item.date">{{ item.date }}</span></div>
          </div>
        </article>

        <article class="chart-card distribution-card">
          <h2>仪器状态分布</h2>
          <div class="donut-layout">
            <div class="donut" :style="donutStyle"><strong>{{ instruments.length }}</strong><span>总数</span></div>
            <ul><li><i class="running"></i>运行中 <strong>{{ runningCount }} 台 ({{ percentage(runningCount) }}%)</strong></li><li><i class="idle"></i>空闲 <strong>{{ idleCount }} 台 ({{ percentage(idleCount) }}%)</strong></li><li><i class="maint"></i>维护/故障 <strong>{{ maintenanceCount }} 台 ({{ percentage(maintenanceCount) }}%)</strong></li></ul>
          </div>
        </article>

        <article class="chart-card completion-card">
          <h2>任务完成概览</h2>
          <div class="completion-content">
            <div class="completion-ring" :style="completionRingStyle"><div><strong>{{ completionRate }}%</strong><span>本周完成率</span></div></div>
            <ul><li><i class="done"></i>已完成任务 <strong>{{ completion.completed }}</strong><small>项</small></li><li><i class="pending"></i>待执行任务 <strong>{{ completion.pending }}</strong><small>项</small></li><li><i class="late"></i>延期任务 <strong>{{ completion.late }}</strong><small>项</small></li></ul>
            <div class="bar-chart"><span>近7天任务完成趋势</span><div class="bars"><i v-for="item in completion.days" :key="item.date" :style="{ height: `${barHeight(item.value)}%` }"><b>{{ item.value }}</b><small>{{ item.date }}</small></i></div></div>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs, { type Dayjs } from 'dayjs'
import { CalendarOutlined, ClockCircleOutlined, DashboardOutlined, DownOutlined, ExperimentOutlined, SafetyCertificateOutlined, ThunderboltOutlined, ToolOutlined, UserOutlined } from '@ant-design/icons-vue'
import { getDashboard, getInstruments, getLabStatus, getTimeslots, getUtilization, type LabStatusInstrument } from '@/services/api'
import type { DashboardData, Instrument, TimeSlot, UtilizationStats } from '@/types'
import './LabOperationsCockpit.css'

interface CockpitInstrument extends LabStatusInstrument { model: string | null; availability_status: Instrument['availability_status'] }
interface TrendItem { date: string; value: number }
const router = useRouter()
const now = ref(dayjs())
const isLoading = ref(true)
const instruments = ref<CockpitInstrument[]>([])
const utilization = ref<UtilizationStats[]>([])
const slots = ref<TimeSlot[]>([])
const dashboard = ref<DashboardData | null>(null)
const weeklyTrend = ref<TrendItem[]>([])
let clockTimer: ReturnType<typeof setInterval> | undefined
let dataTimer: ReturnType<typeof setInterval> | undefined
const INSTRUMENT_IMAGES: Record<string, string> = {
  'ZBYY-002-0001': '/assets/instruments/ab-api5500.png',
  'ZBYY-002-0002': '/assets/instruments/agilent-7000b.png',
  'ZBYY-002-0004': '/assets/instruments/shimadzu-lcms-8050-0004.png',
  'ZBYY-002-0005': '/assets/instruments/shimadzu-lcms-8050-0005.png',
  'ZBYY-002-0006': '/assets/instruments/agilent-7800-icp-ms.png',
  'ZBYY-002-0007': '/assets/instruments/shimadzu-gcms-tq8050-nx.png',
  'ZBYY-002-0011': '/assets/instruments/ab-api5500-plus.png',
}

const currentUserLabel = computed(() => { try { const user = JSON.parse(localStorage.getItem('user') || '{}') as { display_name?: string; username?: string }; return user.display_name || user.username || '系统管理员' } catch { return '系统管理员' } })
const runningCount = computed(() => instruments.value.filter(item => statusClass(item) === 'running').length)
const idleCount = computed(() => instruments.value.filter(item => statusClass(item) === 'idle').length)
const maintenanceCount = computed(() => instruments.value.filter(item => ['maint', 'fault'].includes(statusClass(item))).length)
const averageUtilization = computed(() => roundedRate(dashboard.value?.avg_utilization || 0))
const delayedCount = computed(() => dashboard.value?.delayed_tasks || 0)
const kpis = computed(() => [
  { label: '仪器总数', value: instruments.value.length, unit: '台', icon: ExperimentOutlined, tone: 'blue' },
  { label: '运行中', value: runningCount.value, unit: '台', icon: ThunderboltOutlined, tone: 'green' },
  { label: '空闲仪器', value: idleCount.value, unit: '台', icon: DashboardOutlined, tone: 'blue' },
  { label: '维护/故障', value: maintenanceCount.value, unit: '台', icon: ToolOutlined, tone: 'orange' },
  { label: '平均利用率', value: averageUtilization.value, unit: '%', icon: DashboardOutlined, tone: 'blue' },
  { label: '延期任务', value: delayedCount.value, unit: '项', icon: ClockCircleOutlined, tone: 'purple' },
])
const statusOverview = computed(() => [
  { label: '运行中仪器', value: runningCount.value, unit: '台', note: `占比 ${percentage(runningCount.value)}%`, icon: ThunderboltOutlined, tone: 'green' },
  { label: '空闲仪器', value: idleCount.value, unit: '台', note: `占比 ${percentage(idleCount.value)}%`, icon: DashboardOutlined, tone: 'blue' },
  { label: '维护/故障仪器', value: maintenanceCount.value, unit: '台', note: `占比 ${percentage(maintenanceCount.value)}%`, icon: ToolOutlined, tone: 'orange' },
  { label: '告警与异常', value: delayedCount.value, unit: '条', note: delayedCount.value ? '需关注' : '当前无异常', icon: ClockCircleOutlined, tone: 'red' },
])
const topInstruments = computed(() => [...utilization.value].sort((a, b) => b.actual_utilization_rate - a.actual_utilization_rate).slice(0, 3))
const hasWarning = computed(() => delayedCount.value > 0 || maintenanceCount.value > 0)
const healthDescription = computed(() => hasWarning.value ? `当前有 ${delayedCount.value + maintenanceCount.value} 项需要关注` : '当前无告警与异常事件')
const utilizationMap = computed(() => new Map(utilization.value.map(item => [item.instrument_id, roundedRate(item.actual_utilization_rate)])))

const completion = computed(() => {
  const start = dayjs().startOf('day').subtract(6, 'day')
  const recent = slots.value.filter(slot => dayjs(slot.actual_end || slot.plan_end).isAfter(start))
  const completed = recent.filter(slot => slot.status === 'completed').length
  const pending = recent.filter(slot => ['scheduled', 'running', 'frozen'].includes(slot.status)).length
  const late = recent.filter(slot => ['blocked', 'interrupted'].includes(slot.status) || Number(slot.delay_hours) > 0).length
  const days = Array.from({ length: 7 }, (_, index) => { const date = start.add(index, 'day'); return { date: date.format('MM-DD'), value: recent.filter(slot => slot.status === 'completed' && dayjs(slot.actual_end || slot.plan_end).isSame(date, 'day')).length } })
  return { completed, pending, late, days }
})
const completionRate = computed(() => { const total = completion.value.completed + completion.value.pending + completion.value.late; return total ? Math.round(completion.value.completed / total * 100) : 100 })
const completionRingStyle = computed(() => ({ background: `conic-gradient(#2878ef 0 ${completionRate.value}%, #e7eef8 ${completionRate.value}% 100%)` }))
const donutStyle = computed(() => { const running = percentage(runningCount.value); const idle = running + percentage(idleCount.value); return { background: `conic-gradient(#32b86b 0 ${running}%, #4388ef ${running}% ${idle}%, #f59a3c ${idle}% 100%)` } })
const trendPoints = computed(() => weeklyTrend.value.map((item, index) => `${trendX(index)},${trendY(item.value)}`).join(' '))
const trendAreaPath = computed(() => weeklyTrend.value.length ? `M ${trendX(0)} ${trendY(weeklyTrend.value[0].value)} ${weeklyTrend.value.map((item, index) => `L ${trendX(index)} ${trendY(item.value)}`).join(' ')} L ${trendX(weeklyTrend.value.length - 1)} 100 L ${trendX(0)} 100 Z` : '')

function statusClass(item: CockpitInstrument) { const value = item.status.toLowerCase(); if (value.includes('fault')) return 'fault'; if (value.includes('maint')) return 'maint'; return item.current_task || value === 'running' ? 'running' : 'idle' }
function statusText(item: CockpitInstrument) { return ({ running: '运行中', idle: '空闲', maint: '维护中', fault: '故障' } as const)[statusClass(item) as 'running' | 'idle' | 'maint' | 'fault'] }
function percentage(value: number) { return instruments.value.length ? Math.round(value / instruments.value.length * 1000) / 10 : 0 }
function roundedRate(value: number) { return Math.max(0, Math.min(100, Math.round(Number(value) || 0))) }
function utilizationRate(id: number) { return utilizationMap.value.get(id) || 0 }
function instrumentImage(code: string) { return INSTRUMENT_IMAGES[code] || '/assets/instruments/ab-api5500.png' }
function instrumentCardClass(code: string) {
  if (code === 'ZBYY-002-0007') return 'instrument-card-wide'
  if (code === 'ZBYY-002-0011') return 'instrument-card-wider'
  return ''
}
function instrumentPhotoClass(code: string) {
  const classes = [`instrument-photo-${code.slice(-4)}`]
  if (code === 'ZBYY-002-0006') classes.push('instrument-photo-needs-cleanup')
  return classes
}
function instrumentModel(id: number) { return instruments.value.find(item => item.id === id)?.model }
function trendX(index: number) { return weeklyTrend.value.length > 1 ? 18 + index * (584 / (weeklyTrend.value.length - 1)) : 310 }
function trendY(value: number) { return 100 - Math.max(0, Math.min(100, value)) * .86 }
function barHeight(value: number) { const max = Math.max(...completion.value.days.map(item => item.value), 1); return Math.max(8, value / max * 78) }
function handleUserMenu({ key }: { key: string }) { if (key === 'home') router.push('/operations/lab-dashboard'); if (key === 'logout') { localStorage.removeItem('token'); localStorage.removeItem('user'); router.push('/login') } }
function mergeInstruments(statusList: LabStatusInstrument[], baseList: Instrument[]) { const base = new Map(baseList.map(item => [item.id, item])); return statusList.filter(item => base.get(item.id)?.availability_status === 'available').map(item => ({ ...item, model: base.get(item.id)?.model || null, availability_status: 'available' as const })) }
async function loadData() {
  try {
    const [dashboardData, statusList, baseList, utilizationList, timeSlots] = await Promise.all([getDashboard(), getLabStatus(), getInstruments({ include_unavailable: true }), getUtilization(), getTimeslots()])
    dashboard.value = dashboardData; instruments.value = mergeInstruments(statusList, baseList); utilization.value = utilizationList; slots.value = timeSlots
    const start = dayjs().startOf('day').subtract(6, 'day')
    const daily = await Promise.all(Array.from({ length: 7 }, (_, index) => { const day = start.add(index, 'day'); const end = day.isSame(dayjs(), 'day') ? dayjs() : day.endOf('day'); return getDashboard({ start_date: day.format('YYYY-MM-DDTHH:mm:ss'), end_date: end.format('YYYY-MM-DDTHH:mm:ss') }).then(data => ({ date: day.format('MM-DD'), value: roundedRate(data.avg_utilization) })).catch(() => ({ date: day.format('MM-DD'), value: 0 })) }))
    weeklyTrend.value = daily
  } finally { isLoading.value = false }
}
onMounted(() => { loadData(); clockTimer = setInterval(() => { now.value = dayjs() }, 1000); dataTimer = setInterval(loadData, 60000) })
onBeforeUnmount(() => { if (clockTimer) clearInterval(clockTimer); if (dataTimer) clearInterval(dataTimer) })
</script>
