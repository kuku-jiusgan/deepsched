<template>
  <div class="lab-screen">
    <!-- Background image container -->
    <div class="bg-container" ref="bgRef">
      <img
        :src="bgImage"
        alt="实验室布局图"
        class="bg-image"
        @load="onImageLoad"
      />

      <!-- Instrument status labels - positioned absolutely over the image -->
      <div
        v-for="inst in instruments"
        :key="inst.id"
        class="inst-label"
        :class="labelClass(inst)"
        :style="getLabelStyle(inst)"
        @click="selected = inst"
        :title="inst.name"
      >
        <div class="lbl-status-dot" :class="dotClass(inst)"></div>
        <div class="lbl-code">{{ inst.code }}</div>
        <div v-if="inst.current_task" class="lbl-task">{{ inst.current_task }}</div>
        <div v-if="inst.current_project" class="lbl-proj">{{ inst.current_project }}</div>
        <div v-if="inst.progress !== null && inst.current_task" class="lbl-prog">
          <div class="lbl-prog-bar" :style="{ width: inst.progress + '%' }"></div>
        </div>
        <div v-if="inst.status === 'fault'" class="lbl-badge fault">故障</div>
        <div v-else-if="inst.status === 'maintenance'" class="lbl-badge maint">维护</div>
        <div v-else-if="inst.current_task" class="lbl-badge running">运行</div>
        <div v-else class="lbl-badge idle">空闲</div>
      </div>
    </div>

    <!-- Detail popup -->
    <div v-if="selected" class="detail-popup">
      <div class="dp-head">
        <span class="dp-dot" :class="dotClass(selected)"></span>
        <strong>{{ selected.code }}</strong>
        <span class="dp-close" @click="selected = null">X</span>
      </div>
      <div class="dp-name">{{ selected.name }}</div>
      <div class="dp-row"><span>位置</span><span>{{ selected.location || '-' }}</span></div>
      <div class="dp-row"><span>分组</span><span>{{ selected.group === 'GTI_Group' ? '基因毒组' : '质量组' }}</span></div>
      <div class="dp-row"><span>状态</span><span :style="{ color: statusColor(selected) }">{{ statusText(selected) }}</span></div>
      <div class="dp-row"><span>缓冲率</span><span>{{ selected.buffer_rate }}</span></div>
      <template v-if="selected.current_task">
        <div class="dp-div"></div>
        <div class="dp-row"><span>当前任务</span><span>{{ selected.current_task }}</span></div>
        <div class="dp-row"><span>所属项目</span><span>{{ selected.current_project }}</span></div>
        <div class="dp-row"><span>进度</span><span>{{ selected.progress }}%</span></div>
      </template>
      <div v-if="selected.next_task" class="dp-row"><span>下一任务</span><span>{{ selected.next_task }}</span></div>
    </div>

    <!-- Stats bar -->
    <div class="stats-bar">
      <span class="st running">运行中 {{ runningCount }}</span>
      <span class="st idle">闲置 {{ idleCount }}</span>
      <span class="st warn">维护/故障 {{ maintCount }}</span>
      <span style="margin-left: auto; color: #64748b; font-size: 12px">每 30 秒刷新 · {{ lastRefresh }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import axios from 'axios'
import dayjs from 'dayjs'

interface Inst {
  id: number; code: string; name: string; group: string; location: string | null
  status: string; buffer_rate: number; current_task: string | null
  current_project: string | null; progress: number | null
  next_task: string | null; next_start: string | null
  label_x?: number; label_y?: number  // pixel position on image
}

const instruments = ref<Inst[]>([])
const loading = ref(true)
const lastRefresh = ref('')
const selected = ref<Inst | null>(null)
const bgRef = ref<HTMLElement | null>(null)
const imageLoaded = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

// Replace with your actual lab photo path
const bgImage = ref('/模型贴纸.png')

const runningCount = computed(() => instruments.value.filter(i => i.current_task).length)
const idleCount = computed(() => instruments.value.filter(i => !i.current_task && i.status !== 'maintenance' && i.status !== 'fault').length)
const maintCount = computed(() => instruments.value.filter(i => i.status === 'maintenance' || i.status === 'fault').length)

function labelClass(inst: Inst) {
  if (inst.status === 'fault') return 'fault'
  if (inst.status === 'maintenance') return 'maint'
  if (inst.current_task) return 'running'
  return 'idle'
}

function dotClass(inst: Inst) {
  if (inst.current_task) return 'd-running'
  if (inst.status === 'fault') return 'd-fault'
  if (inst.status === 'maintenance') return 'd-maint'
  return 'd-idle'
}

function statusText(inst: Inst) {
  if (inst.current_task) return '运行中'
  if (inst.status === 'fault') return '故障停机'
  if (inst.status === 'maintenance') return '维护中'
  return '闲置'
}

function statusColor(inst: Inst) {
  if (inst.current_task) return '#16a34a'
  if (inst.status === 'fault') return '#dc2626'
  if (inst.status === 'maintenance') return '#ea580c'
  return '#2563eb'
}

function getLabelStyle(inst: Inst) {
  // Default positions - can be overridden by backend data (label_x, label_y)
  // or manually configured per instrument
  const x = inst.label_x ?? 0
  const y = inst.label_y ?? 0
  return { left: x + 'px', top: y + 'px' }
}

function onImageLoad() {
  imageLoaded.value = true
}

async function fetchData() {
  try {
    const token = localStorage.getItem('token')
    const r = await axios.get('/api/v1/stats/lab-status', { params: { token } })
    // Auto-assign grid positions if no label_x/y
    const data = r.data as Inst[]
    data.forEach((inst, i) => {
      if (inst.label_x === undefined) {
        inst.label_x = 20 + (i % 4) * 220
        inst.label_y = 20 + Math.floor(i / 4) * 140
      }
    })
    instruments.value = data
    lastRefresh.value = dayjs().format('HH:mm:ss')
  } catch { message.error('加载失败') } finally { loading.value = false }
}

onMounted(() => { fetchData(); timer = setInterval(fetchData, 30000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.lab-screen {
  height: calc(100vh - 120px);
  background: #0f172a;
  margin: -24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.bg-container {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
}

.bg-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
}

/* Instrument labels */
.inst-label {
  position: absolute;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
  min-width: 100px;
  z-index: 10;
}

.inst-label:hover { border-color: #60a5fa; background: rgba(15, 23, 42, 0.95); transform: scale(1.03); }
.inst-label.running { border-color: rgba(34,197,94,0.5); }
.inst-label.fault { border-color: rgba(239,68,68,0.6); animation: fault-pulse 1.5s infinite; }
.inst-label.maint { border-color: rgba(249,115,22,0.5); }

@keyframes fault-pulse {
  0%, 100% { box-shadow: 0 0 0 rgba(239,68,68,0); }
  50% { box-shadow: 0 0 12px rgba(239,68,68,0.3); }
}

.lbl-status-dot {
  position: absolute;
  top: 6px; right: 6px;
  width: 6px; height: 6px;
  border-radius: 50%;
}
.d-running { background: #22c55e; box-shadow: 0 0 4px #22c55e; }
.d-idle { background: #3b82f6; }
.d-fault { background: #ef4444; box-shadow: 0 0 4px #ef4444; animation: blink 1s infinite; }
.d-maint { background: #f97316; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

.lbl-code { font-family: monospace; font-size: 11px; font-weight: 600; color: #93c5fd; }
.lbl-task { font-size: 11px; color: #e2e8f0; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lbl-proj { font-size: 10px; color: #64748b; }
.lbl-prog { height: 2px; background: #1e293b; border-radius: 1px; margin-top: 3px; overflow: hidden; }
.lbl-prog-bar { height: 100%; background: #22c55e; border-radius: 1px; transition: width 2s; }
.lbl-badge { font-size: 9px; padding: 1px 5px; border-radius: 3px; margin-top: 3px; display: inline-block; font-weight: 500; }
.lbl-badge.running { background: rgba(34,197,94,0.15); color: #4ade80; }
.lbl-badge.idle { background: rgba(59,130,246,0.15); color: #60a5fa; }
.lbl-badge.fault { background: rgba(239,68,68,0.15); color: #f87171; }
.lbl-badge.maint { background: rgba(249,115,22,0.15); color: #fb923c; }

/* Detail popup */
.detail-popup {
  position: absolute;
  top: 16px; right: 16px;
  width: 240px;
  background: rgba(15, 23, 42, 0.96);
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 14px;
  color: #e2e8f0;
  z-index: 30;
  backdrop-filter: blur(8px);
  font-size: 13px;
}
.dp-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.dp-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dp-close { margin-left: auto; cursor: pointer; color: #64748b; font-size: 14px; }
.dp-name { font-size: 13px; color: #94a3b8; margin-bottom: 10px; }
.dp-row { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; color: #64748b; }
.dp-row span:last-child { color: #cbd5e1; }
.dp-div { height: 1px; background: #1e293b; margin: 6px 0; }

/* Stats bar */
.stats-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 16px;
  background: rgba(15, 23, 42, 0.9);
  border-top: 1px solid #1e293b;
  z-index: 10;
}
.st { padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.st.running { background: rgba(34,197,94,0.12); color: #4ade80; }
.st.idle { background: rgba(59,130,246,0.12); color: #60a5fa; }
.st.warn { background: rgba(239,68,68,0.12); color: #f87171; }
</style>

