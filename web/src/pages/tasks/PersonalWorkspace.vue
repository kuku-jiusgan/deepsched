<template>
  <div>
    <div class="page-header">
      <h2>个人工作台</h2>
    </div>

    <div class="action-bar">
      <a-button @click="fetchData"><ReloadOutlined /> 刷新</a-button>
      <a-tabs v-model:activeKey="activeTab" size="small" style="flex: 1; margin: 0 16px">
        <a-tab-pane key="all" tab="全部" />
        <a-tab-pane key="pending" tab="待处理" />
        <a-tab-pane key="running" tab="进行中" />
        <a-tab-pane key="completed" tab="已完成" />
      </a-tabs>
    </div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 80px auto" />

    <template v-else>
      <TodayTaskCards :tasks="tasks" @complete="handleComplete" @refreshed="fetchData" />

      <a-table :dataSource="filtered" :columns="columns" rowKey="slot_id" size="middle"
        :pagination="{ pageSize: 20, showSizeChanger: true }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'task_type'">
            <a-tag v-if="record.task_type" :color="taskTypeColor(record.task_type)" style="font-size: 11px">{{ taskTypeLabel(record.task_type) }}</a-tag>
            <span v-else style="color: #ccc">-</span>
          </template>
          <template v-else-if="column.key === 'task_name'">
            <span style="font-weight: 500">{{ record.task_name }}</span>
          </template>
          <template v-else-if="column.key === 'project'">
            <span style="font-family: monospace; font-size: 12px; color: #2563eb">{{ record.project_code }}</span>
            <span style="margin-left: 6px; font-size: 12px; color: #64748b">{{ record.project_name }}</span>
          </template>
          <template v-else-if="column.key === 'instrument'">
            {{ record.instrument_name || record.instrument_code || '-' }}
          </template>
          <template v-else-if="column.key === 'plan_start'">
            {{ record.plan_start ? dayjs(record.plan_start).format('MM-DD HH:mm') : '-' }}
          </template>
          <template v-else-if="column.key === 'plan_end'">
            {{ record.plan_end ? dayjs(record.plan_end).format('MM-DD HH:mm') : '-' }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <template v-if="!record.slot_id">
              <a-tag color="default">未排程</a-tag>
            </template>
            <a-space v-else :size="4">
              <a-button
                v-if="record.status === 'scheduled' || record.status === 'pending'"
                type="primary"
                size="small"
                class="task-action-button task-action-button-start"
                @click="handleStart(record)"
                :loading="actingId === record.slot_id"
              >
                <PlayCircleOutlined /> 开始
              </a-button>
              <a-popconfirm
                v-if="record.status === 'running'"
                title="确认将该任务标记为已完成？"
                ok-text="确认完成"
                cancel-text="再检查一下"
                placement="topRight"
                @confirm="handleComplete(record)"
              >
                <a-button
                  size="small"
                  class="task-action-button task-action-button-complete"
                  :loading="actingId === record.slot_id"
                >
                  <CheckCircleOutlined /> 完成
                </a-button>
              </a-popconfirm>

            </a-space>
          </template>
        </template>
      </a-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { CheckCircleOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import {
  getMyTasks, startTask, completeTask, getTaskTypes, type MyTask,
} from '@/services/api'
import TodayTaskCards from './TodayTaskCards.vue'
import dayjs from 'dayjs'

const tasks = ref<MyTask[]>([])
const loading = ref(true)
const activeTab = ref<string>('all')
const actingId = ref<number | null>(null)



const filtered = computed(() => {
  if (activeTab.value === 'all') return tasks.value
  if (activeTab.value === 'pending') return tasks.value.filter(t => ['pending', 'scheduled'].includes(t.status))
  if (activeTab.value === 'running') return tasks.value.filter(t => t.status === 'running')
  if (activeTab.value === 'completed') return tasks.value.filter(t => ['done', 'completed'].includes(t.status))
  return tasks.value
})


const taskTypeMap = ref<Record<string, string>>({})

async function loadTaskTypes() {
  try {
    const types = await getTaskTypes()
    const map: Record<string, string> = {}
    types.forEach(t => { map[t.code] = t.name })
    taskTypeMap.value = map
  } catch { /* ignore */ }
}

function statusColor(s: string) {
  const m: Record<string, string> = { pending: '#94a3b8', scheduled: '#2563eb', running: '#16a34a', completed: '#7c3aed', done: '#7c3aed', blocked: '#dc2626', interrupted: '#ea580c' }
  return m[s] || '#94a3b8'
}

function taskTypeLabel(code: string | null) { return code ? (taskTypeMap.value[code] || code) : '' }
function taskTypeColor(code: string | null) {
  if (!code) return '#94a3b8'
      const m: Record<string, string> = { FFKF_001: '#8b5cf6', QCFA_001: '#f59e0b', FFYZ_001: '#10b981', SJCL_001: '#3b82f6', ZXBG_001: '#ef4444' }
  return m[code] || '#94a3b8'
}
function statusLabel(s: string) {
  const m: Record<string, string> = { pending: '待处理', scheduled: '待执行', running: '运行中', completed: '已完成', done: '已完成', blocked: '已延期', interrupted: '已中断' }
  return m[s] || s
}

const columns = [
  { title: '任务名称', dataIndex: 'task_name', key: 'task_name', width: 200, ellipsis: true },
  { title: '任务类型', key: 'task_type', width: 110 },
  { title: '所属项目', key: 'project', width: 200 },
  { title: '仪器', key: 'instrument', width: 130 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '计划开始', key: 'plan_start', width: 120 },
  { title: '计划结束', key: 'plan_end', width: 120 },
  { title: '操作', key: 'actions', width: 160 },
]

async function fetchData() {
  loading.value = true
  try {
    tasks.value = await getMyTasks()
    loadTaskTypes()
  } catch {
    message.error('加载工作台失败')
  } finally {
    loading.value = false
  }
}

async function handleStart(record: MyTask) {
  actingId.value = record.slot_id
  try {
    await startTask(record.slot_id)
    message.success('任务已开始')
    fetchData()
  } catch { message.error('操作失败') }
  finally { actingId.value = null }
}

async function handleComplete(record: MyTask) {
  actingId.value = record.slot_id
  try {
    await completeTask(record.slot_id)
    message.success('任务已完成')
    fetchData()
  } catch { message.error('操作失败') }
  finally { actingId.value = null }
}

onMounted(fetchData)
</script>

<style scoped>
.task-action-button {
  min-width: 72px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.task-action-button-start {
  background: var(--color-accent) !important;
  border-color: var(--color-accent) !important;
}

.task-action-button-complete {
  color: #ffffff !important;
  background: var(--color-success) !important;
  border-color: var(--color-success) !important;
}

.task-action-button-complete:hover,
.task-action-button-complete:focus {
  color: #ffffff !important;
  background: #15803d !important;
  border-color: #15803d !important;
}
</style>
