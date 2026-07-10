<template>
  <div>
    <div class="page-header">
      <h2>插单与影响预览</h2>
      <p>高优项目可顺延低优且未开始的确认/预测任务，冻结和运行中排程不会移动。</p>
    </div>

    <a-card class="insert-card" :bordered="false">
      <a-form layout="vertical">
        <a-form-item label="插单项目" required>
          <a-select
            v-model:value="form.projectId"
            :options="projectOptions"
            placeholder="选择需要插单的项目"
            show-search
            option-filter-prop="label"
            @change="handleProjectChange"
          />
        </a-form-item>
        <a-form-item label="插单任务" required>
          <a-checkbox-group v-model:value="form.taskIds" class="task-options">
            <a-checkbox v-for="task in selectableTasks" :key="task.id" :value="task.id">
              <span class="task-name">{{ task.name }}</span>
              <span class="task-meta">{{ task.est_duration_hours || 0 }}h · {{ statusLabel(task.status) }}</span>
            </a-checkbox>
          </a-checkbox-group>
          <a-empty v-if="form.projectId && !selectableTasks.length" description="该项目暂无可插单的叶子任务" />
        </a-form-item>
        <a-form-item label="临时项目等级" extra="不选择时使用项目当前等级">
          <a-select v-model:value="form.priorityOverride" allowClear :options="priorityOptions" placeholder="使用项目当前等级" />
        </a-form-item>
        <a-space>
          <a-button type="primary" :loading="previewing" @click="loadPreview">计算影响</a-button>
          <a-button @click="resetPreview">清空预览</a-button>
        </a-space>
      </a-form>
    </a-card>

    <a-card v-if="preview" class="preview-card" title="排程影响预览" :bordered="false">
      <a-alert
        type="info"
        show-icon
        :message="`预计创建 ${preview.timeslots_created} 个时间槽，累计顺延 ${preview.total_delay_hours} 小时`"
      />
      <a-table
        :data-source="preview.impacts"
        :columns="impactColumns"
        row-key="task_id"
        size="small"
        :pagination="false"
        style="margin-top: 16px"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            <a-tag :color="record.is_insert_task ? 'blue' : 'orange'">
              {{ record.is_insert_task ? '插单任务' : '顺延任务' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'original'">
            {{ formatRange(record.original_start, record.original_end) }}
          </template>
          <template v-else-if="column.key === 'new'">
            {{ formatRange(record.new_start, record.new_end) }}
          </template>
          <template v-else-if="column.key === 'delay'">
            <span :class="{ 'delay-positive': record.delay_hours > 0 }">{{ record.delay_hours }}h</span>
          </template>
        </template>
      </a-table>
      <div class="preview-actions">
        <a-button @click="router.push('/schedule/engine')">返回排程管理</a-button>
        <a-button type="primary" :loading="confirming" @click="handleConfirm">确认插单</a-button>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import {
  calculateInsertCost,
  confirmInsert,
  getProjects,
  type InsertOrderRequest,
} from '@/services/api'
import type { InsertCost, Project, Task } from '@/types'

interface InsertForm {
  projectId: number | null
  taskIds: number[]
  priorityOverride: number | null
}

const router = useRouter()
const projects = ref<Project[]>([])
const preview = ref<InsertCost | null>(null)
const previewing = ref(false)
const confirming = ref(false)
const form = reactive<InsertForm>({ projectId: null, taskIds: [], priorityOverride: null })
const priorityOptions = [
  { label: '一级（最高）', value: 1 },
  { label: '二级', value: 2 },
  { label: '三级', value: 3 },
]

function priorityLabel(priority: number) {
  return priorityOptions.find(option => option.value === priority)?.label || `${priority}级`
}

const projectOptions = computed(() => projects.value.map(project => ({
  label: `${project.code} · ${project.name}（${priorityLabel(project.priority)}）`,
  value: project.id,
})))

const selectedProject = computed(() => projects.value.find(project => project.id === form.projectId) || null)
const selectableTasks = computed(() => flattenLeafTasks(selectedProject.value?.tasks || []).filter(task =>
  !['running', 'done', 'completed'].includes(task.status),
))

const impactColumns = [
  { title: '类型', key: 'type', width: 100 },
  { title: '项目', dataIndex: 'project_name', key: 'project' },
  { title: '任务', dataIndex: 'task_name', key: 'task' },
  { title: '原排程', key: 'original', width: 240 },
  { title: '新排程', key: 'new', width: 240 },
  { title: '顺延', key: 'delay', width: 90 },
]

onMounted(async () => {
  try {
    projects.value = await getProjects()
  } catch {
    message.error('项目加载失败')
  }
})

function flattenLeafTasks(tasks: Task[]): Task[] {
  return tasks.flatMap(task => task.children?.length ? flattenLeafTasks(task.children) : [task])
}

function handleProjectChange() {
  form.taskIds = []
  form.priorityOverride = null
  preview.value = null
}

function requestData(): InsertOrderRequest | null {
  if (!form.projectId) {
    message.warning('请选择插单项目')
    return null
  }
  if (!form.taskIds.length) {
    message.warning('请选择插单任务')
    return null
  }
  return {
    project_id: form.projectId,
    task_ids: form.taskIds,
    ...(form.priorityOverride ? { priority_override: form.priorityOverride } : {}),
  }
}

async function loadPreview() {
  const data = requestData()
  if (!data) return
  previewing.value = true
  try {
    preview.value = await calculateInsertCost(data)
  } catch {
    message.error('插单影响计算失败')
  } finally {
    previewing.value = false
  }
}

function resetPreview() {
  preview.value = null
}

function handleConfirm() {
  const data = requestData()
  if (!data || !preview.value) return
  Modal.confirm({
    title: '确认执行插单？',
    content: `将创建 ${preview.value.timeslots_created} 个时间槽，并移动 ${preview.value.impacts.filter(item => !item.is_insert_task).length} 个低优任务。`,
    okText: '确认插单',
    cancelText: '取消',
    onOk: () => executeConfirm(data),
  })
}

async function executeConfirm(data: InsertOrderRequest) {
  confirming.value = true
  try {
    const result = await confirmInsert(data)
    message.success(`插单完成，创建 ${result.timeslots_created} 个时间槽`)
    await router.push('/kanban/instrument-gantt')
  } catch {
    message.error('插单执行失败')
  } finally {
    confirming.value = false
  }
}

function formatRange(start: string | null, end: string | null) {
  if (!start || !end) return '未排程'
  return `${dayjs(start).format('MM-DD HH:mm')} – ${dayjs(end).format('MM-DD HH:mm')}`
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待排', ready: '可排', scheduled: '已排程', blocked: '已阻塞',
  }
  return labels[status] || status
}
</script>

<style scoped>
.page-header p { margin: 6px 0 0; color: var(--color-text-secondary); }
.insert-card, .preview-card { max-width: 1100px; margin-top: 16px; }
.task-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; width: 100%; }
.task-options :deep(.ant-checkbox-wrapper) { margin-inline-start: 0; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.task-name { font-weight: 500; }
.task-meta { margin-left: 8px; color: var(--color-text-tertiary); font-size: 12px; }
.preview-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.delay-positive { color: var(--color-danger); font-weight: 600; }
@media (max-width: 760px) { .task-options { grid-template-columns: 1fr; } }
</style>
