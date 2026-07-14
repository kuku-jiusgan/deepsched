<template>
  <div class="lab-screen">
    <header class="screen-head">
      <div>
        <h2>实验室状态大屏</h2>
        <p>一楼、二楼仪器运行态实时总览</p>
      </div>
      <div class="head-actions">
        <a-segmented v-model:value="activeFloor" :options="floorOptions" size="small" />
        <span class="refresh">30 秒刷新 · {{ lastRefresh || '等待数据' }}</span>
      </div>
    </header>

    <section class="summary-strip" aria-label="实验室状态统计">
      <div class="summary-item running"><strong>{{ runningCount }}</strong><span>运行中</span></div>
      <div class="summary-item idle"><strong>{{ idleCount }}</strong><span>空闲可用</span></div>
      <div class="summary-item warn"><strong>{{ warningCount }}</strong><span>维护/故障</span></div>
      <div class="summary-item total"><strong>{{ visibleInstruments.length }}</strong><span>当前显示</span></div>
    </section>

    <main class="map-shell">
      <div v-if="isLoading" class="map-loading"><span></span><span></span><span></span></div>
      <div v-else-if="loadError" class="map-empty">{{ loadError }}</div>

      <div class="map-stage" @click.self="selected = null">
        <img :src="backgroundImage" alt="实验室一楼二楼平面图" class="floor-map" />
        <button
          v-for="point in visiblePoints"
          :key="point.instrument.id"
          class="instrument-point"
          :class="[point.statusClass, { selected: selected?.id === point.instrument.id }]"
          :style="{ left: `${point.x}%`, top: `${point.y}%` }"
          :title="point.instrument.name"
          @click.stop="selectInstrument(point.instrument)"
        >
          <span class="pulse"></span>
          <span class="pin-core">{{ point.instrument.code }}</span>
          <span class="pin-meta">{{ statusText(point.instrument) }}</span>
        </button>
      </div>

      <aside v-if="selected" class="detail-panel">
        <div class="detail-scan"></div>
        <div class="detail-head">
          <span class="detail-dot" :class="dotClass(selected)"></span>
          <div>
            <strong>{{ selected.code }}</strong>
            <span>{{ selected.name }}</span>
          </div>
          <button class="close-btn" type="button" @click="selected = null">×</button>
        </div>

        <div class="detail-status" :class="detailClass(selected)">
          <span>{{ statusText(selected) }}</span>
          <b>{{ selected.progress !== null && selected.current_task ? `${selected.progress}%` : floorLabel(selected) }}</b>
        </div>

        <dl class="detail-grid">
          <div><dt>楼层位置</dt><dd>{{ floorLabel(selected) }} · {{ selected.location || '未标注' }}</dd></div>
          <div><dt>仪器分组</dt><dd>{{ groupText(selected.group) }}</dd></div>
          <div><dt>使用人</dt><dd>{{ selected.current_user || '未分配' }}</dd></div>
          <div><dt>当前项目</dt><dd>{{ selected.current_project || '暂无运行项目' }}</dd></div>
          <div><dt>当前任务</dt><dd>{{ selected.current_task || '未占用' }}</dd></div>
          <div><dt>下一任务</dt><dd>{{ selected.next_task || '暂无待执行任务' }}</dd></div>
        </dl>

        <div class="progress-block">
          <div class="progress-label"><span>运行进度</span><span>{{ selected.progress ?? 0 }}%</span></div>
          <div class="progress-track"><span :style="{ width: `${selected.progress ?? 0}%` }"></span></div>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { getLabStatus, type LabStatusInstrument } from '@/services/api'

type FloorFilter = 'all' | 'floor1' | 'floor2'

interface MapPoint {
  instrument: LabStatusInstrument
  x: number
  y: number
  floor: FloorFilter
  statusClass: string
}

const backgroundImage = '/lab-status/lab-digital-twin.png'
const floorOptions = [
  { label: '总览', value: 'all' },
  { label: '一楼', value: 'floor1' },
  { label: '二楼', value: 'floor2' },
]
const slotPositions = [
  { x: 17.2, y: 76.8, floor: 'floor1' },
  { x: 38.6, y: 77.4, floor: 'floor1' },
  { x: 60.4, y: 77.4, floor: 'floor1' },
  { x: 38.4, y: 32.2, floor: 'floor2' },
  { x: 51.1, y: 32.2, floor: 'floor2' },
  { x: 66.2, y: 32.2, floor: 'floor2' },
  { x: 80.1, y: 32.2, floor: 'floor2' },
] as const

const instruments = ref<LabStatusInstrument[]>([])
const selected = ref<LabStatusInstrument | null>(null)
const activeFloor = ref<FloorFilter>('all')
const isLoading = ref(true)
const loadError = ref('')
const lastRefresh = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const displayInstruments = computed(() => instruments.value.slice(0, slotPositions.length))
const points = computed<MapPoint[]>(() => displayInstruments.value.map((instrument, index) => {
  const savedPosition = savedPoint(instrument)
  const fallback = slotPositions[index % slotPositions.length]
  return {
    instrument,
    x: savedPosition?.x ?? fallback.x,
    y: savedPosition?.y ?? fallback.y,
    floor: savedPosition?.floor ?? fallback.floor,
    statusClass: detailClass(instrument),
  }
}))
const visiblePoints = computed(() => points.value.filter(point => activeFloor.value === 'all' || point.floor === activeFloor.value))
const visibleInstruments = computed(() => visiblePoints.value.map(point => point.instrument))
const runningCount = computed(() => visibleInstruments.value.filter(inst => Boolean(inst.current_task)).length)
const idleCount = computed(() => visibleInstruments.value.filter(inst => detailClass(inst) === 'idle').length)
const warningCount = computed(() => visibleInstruments.value.filter(inst => ['fault', 'maint'].includes(detailClass(inst))).length)

function savedPoint(instrument: LabStatusInstrument) {
  if (!instrument.label_x || !instrument.label_y) return null
  const floor: FloorFilter = instrument.label_x > 50 ? 'floor2' : 'floor1'
  return { x: clamp(instrument.label_x, 4, 96), y: clamp(instrument.label_y, 8, 92), floor }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function detailClass(instrument: LabStatusInstrument) {
  if (instrument.status === 'fault') return 'fault'
  if (instrument.status === 'maintenance') return 'maint'
  if (instrument.current_task) return 'running'
  return 'idle'
}

function dotClass(instrument: LabStatusInstrument) {
  return `dot-${detailClass(instrument)}`
}

function statusText(instrument: LabStatusInstrument) {
  const status = detailClass(instrument)
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

function floorLabel(instrument: LabStatusInstrument) {
  const point = points.value.find(item => item.instrument.id === instrument.id)
  return point?.floor === 'floor2' ? '二楼' : '一楼'
}

function selectInstrument(instrument: LabStatusInstrument) {
  selected.value = instrument
}

async function fetchData() {
  try {
    loadError.value = ''
    instruments.value = await getLabStatus()
    lastRefresh.value = dayjs().format('HH:mm:ss')
    if (selected.value) selected.value = instruments.value.find(item => item.id === selected.value?.id) ?? null
  } catch {
    loadError.value = '实验室状态加载失败'
    message.error('实验室状态加载失败')
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 30000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.lab-screen { min-height: calc(100vh - 112px); margin: -24px; padding: 18px; display: grid; grid-template-rows: auto auto 1fr; gap: 12px; background: #eef4fb; color: #1e293b; overflow: hidden; }
.screen-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 2px 4px; }
.screen-head h2 { margin: 0; font-size: 21px; line-height: 1.2; }
.screen-head p { margin: 5px 0 0; color: #64748b; font-size: 13px; }
.head-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
.refresh { color: #64748b; font-size: 12px; }
.summary-strip { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; }
.summary-item { min-height: 58px; padding: 10px 14px; border: 1px solid #dbe7f3; border-radius: 10px; background: rgba(255,255,255,.78); display: flex; align-items: baseline; gap: 8px; }
.summary-item strong { font-size: 24px; line-height: 1; }
.summary-item span { color: #64748b; font-size: 12px; }
.summary-item.running strong { color: #16a34a; }
.summary-item.idle strong { color: #2563eb; }
.summary-item.warn strong { color: #dc2626; }
.summary-item.total strong { color: #475569; }
.map-shell { position: relative; min-height: 0; border: 1px solid #d4e2f0; border-radius: 14px; background: linear-gradient(180deg, #f8fbff 0%, #e9f1fa 100%); overflow: hidden; }
.map-stage { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 12px; }
.floor-map { width: 100%; height: 100%; object-fit: contain; filter: saturate(.95) contrast(1.02); user-select: none; pointer-events: none; }
.instrument-point { position: absolute; transform: translate(-50%, -50%); width: 104px; height: 78px; border: 0; background: transparent; color: #1e293b; padding: 0; cursor: pointer; transition: transform .18s ease, filter .18s ease; display: grid; place-items: center; }
.instrument-point::before { content: ""; width: 24px; height: 24px; border-radius: 50%; border: 2px solid rgba(255,255,255,.9); background: #2563eb; box-shadow: 0 0 0 8px rgba(37,99,235,.16), 0 0 22px rgba(37,99,235,.44); }
.instrument-point:hover, .instrument-point.selected { transform: translate(-50%, -50%) scale(1.08); filter: brightness(1.04); z-index: 8; }
.pin-core { position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); max-width: 96px; padding: 3px 7px; border: 1px solid rgba(148,163,184,.35); border-radius: 6px; background: rgba(255,255,255,.9); font-family: var(--font-mono); font-size: 11px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; box-shadow: 0 2px 8px rgba(15,23,42,.08); }
.pin-meta { position: absolute; top: 0; left: 50%; transform: translateX(-50%); padding: 2px 6px; border-radius: 999px; background: rgba(255,255,255,.78); font-size: 10px; color: #64748b; white-space: nowrap; }
.pulse { position: absolute; top: 50%; left: 50%; width: 58px; height: 58px; border-radius: 50%; transform: translate(-50%, -50%); opacity: .34; }
.running::before { background: #16a34a; box-shadow: 0 0 0 8px rgba(22,163,74,.16), 0 0 24px rgba(22,163,74,.52); }
.fault::before { background: #dc2626; box-shadow: 0 0 0 8px rgba(220,38,38,.16), 0 0 24px rgba(220,38,38,.55); }
.maint::before { background: #ea580c; box-shadow: 0 0 0 8px rgba(234,88,12,.16), 0 0 24px rgba(234,88,12,.46); }
.running .pulse { background: rgba(22,163,74,.18); animation: state-pulse 1.8s ease-out infinite; }
.fault .pulse { background: rgba(220,38,38,.2); animation: state-pulse 1.2s ease-out infinite; }
.maint .pulse { background: rgba(234,88,12,.16); }
.idle .pulse { background: rgba(37,99,235,.12); }
.detail-panel { position: absolute; top: 18px; right: 18px; width: min(360px, calc(100% - 36px)); padding: 16px; border: 1px solid rgba(37,99,235,.24); border-radius: 14px; background: rgba(248,251,255,.95); box-shadow: 0 18px 36px rgba(30,41,59,.16); overflow: hidden; animation: panel-in .18s ease-out; z-index: 12; }
.detail-scan { position: absolute; inset: 0; background: linear-gradient(110deg, transparent 0 42%, rgba(37,99,235,.12) 48%, transparent 56%); transform: translateX(-100%); animation: scan 2.8s ease-in-out infinite; pointer-events: none; }
.detail-head { position: relative; display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.detail-head strong { display: block; font-family: var(--font-mono); font-size: 15px; }
.detail-head span { display: block; color: #64748b; font-size: 12px; }
.detail-dot { width: 10px; height: 10px; border-radius: 50%; flex: 0 0 auto; }
.dot-running { background: #16a34a; box-shadow: 0 0 0 5px rgba(22,163,74,.12); }
.dot-idle { background: #2563eb; box-shadow: 0 0 0 5px rgba(37,99,235,.12); }
.dot-fault { background: #dc2626; box-shadow: 0 0 0 5px rgba(220,38,38,.12); }
.dot-maint { background: #ea580c; box-shadow: 0 0 0 5px rgba(234,88,12,.12); }
.close-btn { margin-left: auto; border: 0; background: #e2e8f0; border-radius: 6px; width: 26px; height: 26px; cursor: pointer; color: #475569; }
.detail-status { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 10px; margin-bottom: 12px; font-size: 13px; }
.detail-status.running { background: #f0fdf4; color: #15803d; }
.detail-status.idle { background: #eff6ff; color: #1d4ed8; }
.detail-status.fault { background: #fef2f2; color: #b91c1c; }
.detail-status.maint { background: #fff7ed; color: #c2410c; }
.detail-grid { display: grid; gap: 9px; margin: 0; }
.detail-grid div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 10px; }
.detail-grid dt { color: #94a3b8; font-size: 12px; }
.detail-grid dd { margin: 0; color: #334155; font-size: 13px; overflow-wrap: anywhere; }
.progress-block { margin-top: 14px; }
.progress-label { display: flex; justify-content: space-between; color: #64748b; font-size: 12px; margin-bottom: 6px; }
.progress-track { height: 7px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: #16a34a; transition: width .3s ease; }
.map-loading, .map-empty { position: absolute; inset: 0; z-index: 20; display: flex; align-items: center; justify-content: center; color: #64748b; background: rgba(248,251,255,.74); }
.map-loading { gap: 7px; }
.map-loading span { width: 9px; height: 9px; border-radius: 50%; background: #2563eb; animation: bounce 1s infinite ease-in-out; }
.map-loading span:nth-child(2) { animation-delay: .12s; }
.map-loading span:nth-child(3) { animation-delay: .24s; }
@keyframes state-pulse { from { transform: scale(.9); opacity: .5; } to { transform: scale(1.35); opacity: 0; } }
@keyframes panel-in { from { opacity: 0; transform: translateX(12px); } to { opacity: 1; transform: translateX(0); } }
@keyframes scan { 0%, 45% { transform: translateX(-100%); } 70%, 100% { transform: translateX(100%); } }
@keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: .5; } 40% { transform: translateY(-7px); opacity: 1; } }
@media (max-width: 960px) {
  .lab-screen { margin: -16px; padding: 12px; min-height: calc(100vh - 88px); }
  .screen-head { flex-direction: column; }
  .head-actions { justify-content: flex-start; }
  .summary-strip { grid-template-columns: repeat(2, 1fr); }
  .instrument-point { width: 72px; height: 58px; }
  .instrument-point::before { width: 18px; height: 18px; }
  .pin-core { font-size: 10px; }
  .pin-meta { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .pulse, .detail-scan, .map-loading span { animation: none; }
  .instrument-point, .detail-panel, .progress-track span { transition: none; }
}
</style>
