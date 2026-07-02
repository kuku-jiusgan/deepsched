<template>
  <div>
    <div class="page-header">
      <h2>个人工作台</h2>
    </div>

    <div class="action-bar">
      <a-button @click="fetchData"><ReloadOutlined /> 刷新</a-button>
      <a-select v-model:value="statusFilter" placeholder="状态筛选" allowClear style="width: 140px" :options="statusOptions" />
      <span style="margin-left: auto; font-size: 12px; color: #94a3b8; align-self: center">
        共 {{ filtered.length }} 个任务
      </span>
    </div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 80px auto" />

    <a-table v-else :dataSource="filtered" :columns="columns" rowKey="slot_id" size="middle"
      :pagination="{ pageSize: 20, showSizeChanger: true }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
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
              type="primary" size="small"
              @click="handleStart(record)"
              :loading="actingId === record.slot_id"
            >开始</a-button>
            <a-button
              v-if="record.status === 'running'"
              type="primary" size="small"
              style="background: #16a34a; border-color: #16a34a"
              @click="handleComplete(record)"
              :loading="actingId === record.slot_id"
            >完成</a-button>
            <a-button
              v-if="record.status === 'running' || record.status === 'scheduled'"
              size="small"
              danger
              @click="handleDelay(record)"
              :loading="actingId === record.slot_id"
            >延期</a-button>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getMyTasks, startTask, completeTask, interruptTask, type MyTask } from '@/services/api'
import dayjs from 'dayjs'

const tasks = ref<MyTask[]>([])
const loading = ref(true)
const statusFilter = ref<string | undefined>(undefined)
const actingId = ref<number | null>(null)

const statusOptions = [
  { label: '待处理', value: 'pending' },
  { label: '待执行', value: 'scheduled' },
  { label: '运行中', value: 'running' },
  { label: '已延期', value: 'blocked' },
  { label: '已中断', value: 'interrupted' },
]

const filtered = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter(t => t.status === statusFilter.value)
})

function statusColor(s: string) {
  const m: Record<string, string> = { pending: '#94a3b8', scheduled: '#2563eb', running: '#16a34a', completed: '#7c3aed', blocked: '#dc2626', interrupted: '#ea580c' }
  return m[s] || '#94a3b8'
}

function statusLabel(s: string) {
  const m: Record<string, string> = { pending: '待处理', scheduled: '待执行', running: '运行中', completed: '已完成', blocked: '已延期', interrupted: '已中断' }
  return m[s] || s
}

const columns = [
  { title: '任务名称', dataIndex: 'task_name', key: 'task_name', width: 200, ellipsis: true },
  { title: '所属项目', key: 'project', width: 200 },
  { title: '仪器', key: 'instrument', width: 130 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '计划开始', key: 'plan_start', width: 120 },
  { title: '计划结束', key: 'plan_end', width: 120 },
  { title: '操作', key: 'actions', width: 160 },
]

async function fetchData() {
  loading.value = true
  try { tasks.value = await getMyTasks() } catch { message.error('加载任务失败') } finally { loading.value = false }
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

async function handleDelay(record: MyTask) {
  actingId.value = record.slot_id
  try {
    await interruptTask(record.slot_id)
    message.warning('已汇报延期')
    fetchData()
  } catch { message.error('操作失败') }
  finally { actingId.value = null }
}

onMounted(fetchData)
</script>
