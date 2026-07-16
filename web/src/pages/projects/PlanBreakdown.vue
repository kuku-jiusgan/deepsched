<template>
  <div>
    <div class="page-header">
      <a-button type="text" @click="goBack"><LeftOutlined /> 返回</a-button>
      <h2 style="margin: 0 0 0 8px">{{ project?.name || '项目计划拆解' }}</h2>
      <a-tag v-if="project" :color="project.status === 'active' ? '#16a34a' : '#94a3b8'" style="margin-left: 12px">{{ statusLabels[project.status] || project.status }}</a-tag>
    </div>
    <a-spin v-if="loading" size="large" style="display: block; margin: 50px auto" />
    <template v-else-if="project">
      <div class="project-info">
        <a-descriptions :column="4" size="small" bordered>
          <a-descriptions-item label="项目编号">{{ project.code }}</a-descriptions-item>
          <a-descriptions-item label="客户">{{ project.client_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="负责人">{{ project.manager_name || '-' }}</a-descriptions-item>
          <a-descriptions-item label="项目优先级"><a-tag :color="priorityColor(project.priority)">{{ priorityLabel(project.priority) }}</a-tag></a-descriptions-item>
          <a-descriptions-item label="项目预计工时">{{ project.estimated_hours != null ? `${project.estimated_hours} 小时` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="开始日期">{{ project.start_date ? dayjs(project.start_date).format('YYYY-MM-DD') : '-' }}</a-descriptions-item>
          <a-descriptions-item label="结题日期">{{ project.end_date ? dayjs(project.end_date).format('YYYY-MM-DD') : '-' }}</a-descriptions-item>
        </a-descriptions>
      </div>
      <a-alert
        v-if="hasLocalDrafts"
        type="info"
        showIcon
        message="当前有未保存的计划草稿"
        description="新增任务和模板计划目前只保存在本页面；离开页面将丢失，点击“保存并开始排程”后才会写入数据库。"
        style="margin-bottom: 16px"
      />
      <a-alert
        v-else-if="hasPendingPlanChanges"
        type="warning"
        showIcon
        message="计划已修改，待重新排程"
        description="当前甘特图仍保留原排程；只有点击“保存并开始排程”后才会应用新计划。"
        style="margin-bottom: 16px"
      />
      <div class="action-bar">
        <a-button type="primary" @click="openAddTask(null)"><PlusOutlined /> 添加顶级任务</a-button>
        <a-button @click="openTemplateImport"><ImportOutlined /> 模板计划导入</a-button>
        <a-button @click="openApprovalGate"><FileTextOutlined /> 添加方案签批</a-button>
        <span style="margin-left: 8px; font-size: 12px; color: #94a3b8">点击左侧 &gt; 展开/收起子任务</span>
        <span style="margin-left: auto; font-size: 12px; color: #94a3b8">{{ flatTaskCount }} 个任务（{{ leafTaskCount }} 个叶子任务）</span>
      </div>
      <a-table v-model:expandedRowKeys="expandedTaskIds" :dataSource="treeTasks" rowKey="id" size="small" :pagination="{ pageSize: 50, showSizeChanger: true }"
        :indentSize="24">
        <a-table-column title="任务名称" dataIndex="name" key="name">
          <template #default="{ record }">
            <span :style="{ fontWeight: record.children?.length ? 600 : 400 }">{{ record.name }}</span>
              <a-tag v-if="record.is_local_draft" color="blue" style="margin-left: 8px">未保存</a-tag>
              <a-tag v-else-if="record.schedule_dirty" color="orange" style="margin-left: 8px">待重新排程</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="类型" key="task_type" width="120">
          <template #default="{ record }">
            <a-tag v-if="record.is_external_gate" color="default" style="font-size: 11px">方案签批</a-tag>
            <a-tag v-else-if="!record.children?.length" :color="getTaskTypeColor(record.task_type)" style="font-size: 11px">{{ getTaskTypeName(record.task_type) }}</a-tag>
          </template>
        </a-table-column>
        <a-table-column title="状态/签批时间" key="plan_status" width="175">
          <template #default="{ record }">
            <template v-if="record.is_external_gate">
              <a-tag :color="gateStatusMeta(record.gate_status).color">{{ gateStatusMeta(record.gate_status).label }}</a-tag>
              <div style="margin-top: 3px; color: #64748b; font-size: 11px">{{ gateDateText(record) }}</div>
            </template>
            <span v-else>{{ taskStatusLabel(record.status) }}</span>
          </template>
        </a-table-column>
        <a-table-column title="对应仪器" key="instruments" width="180">
          <template #default="{ record }">
            <div v-if="getTaskInstrumentIds(record).length" class="instrument-tag-list">
              <a-tooltip
                v-for="instId in getTaskInstrumentIds(record).slice(0, 2)"
                :key="instId"
                :title="getInstrumentCode(instId)"
              >
                <a-tag color="blue" class="instrument-tag">{{ getInstrumentCode(instId) }}</a-tag>
              </a-tooltip>
              <a-tooltip v-if="getTaskInstrumentIds(record).length > 2" :title="getInstrumentSummary(record)">
                <a-tag class="instrument-tag">+{{ getTaskInstrumentIds(record).length - 2 }}</a-tag>
              </a-tooltip>
            </div>
            <span v-else-if="!record.children?.length && record.requires_instrument" style="color: #dc2626">未指定</span>
            <span v-else style="color: #ccc">-</span>
          </template>
        </a-table-column>
        <a-table-column title="负责人" key="assignee" width="100">
          <template #default="{ record }">{{ !record.children?.length ? (record.assignee_name || getAssigneeName(record.assignee_id) || '-') : '' }}</template>
        </a-table-column>
        <a-table-column title="耗时(h)" key="dur" width="90" align="center">
          <template #default="{ record }">{{ !record.children?.length ? (record.est_duration_hours || '-') : sumChildrenHours(record).toFixed(1) }}</template>
        </a-table-column>
        <a-table-column title="前置任务" key="predecessors" width="160">
          <template #default="{ record }">
            <span v-if="record.predecessor_ids?.length && !record.children?.length">
              <a-tag v-for="pid in record.predecessor_ids" :key="pid" color="blue" style="font-size: 10px; margin: 1px">{{ getTaskNameById(pid) }}</a-tag>
            </span>
            <span v-else style="color: #ccc">-</span>
          </template>
        </a-table-column>
        <a-table-column title="操作" key="actions" width="180">
          <template #default="{ record }">
            <a-space v-if="record.is_external_gate && record.is_local_draft" :size="0">
              <a-popconfirm title="确定删除这个未保存的方案签批？" @confirm="handleDeleteTask(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
            <a-space v-else-if="record.is_external_gate" :size="0">
              <a-popconfirm title="确定删除方案签批？删除后下游任务将恢复为待排程状态。" @confirm="handleDeleteTask(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
            <a-space v-else :size="0">
              <a-button type="link" size="small" @click="openAddTask(record.id)" title="添加子任务"><PlusOutlined /></a-button>
              <a-button type="link" size="small" @click="openEditTask(record)"><EditOutlined /></a-button>
              <a-popconfirm title="确定删除该任务及其所有子任务？" @confirm="handleDeleteTask(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table-column>
      </a-table>
      <div style="margin-top: 16px; text-align: right">
        <a-button type="primary" size="large" @click="handleStartSchedule" :loading="scheduling">
          <PlayCircleOutlined /> 保存并开始排程
        </a-button>
      </div>
    </template>
    <a-modal :title="editingTask ? '编辑任务' : '添加任务'" v-model:open="taskOpen" @ok="handleTaskSubmit" width="500" :okText="editingTask ? '保存' : '添加'">
      <a-form layout="vertical" :labelCol="{ style: { paddingBottom: 0 } }">
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="父任务"><a-select v-model:value="tf.parent_id" :options="parentTaskOptions" placeholder="顶级任务" allowClear :disabled="!!parentTaskId || !canEditScheduleFields" size="small" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="任务名称" required><a-input v-model:value="tf.name" placeholder="输入名称" size="small" /></a-form-item>
          </a-col>
        </a-row>
        <a-row v-if="!isEditingParent" :gutter="12">
          <a-col :span="6">
            <a-form-item label="任务类型" required><a-select v-model:value="tf.task_type" :options="taskTypeOptions" placeholder="选择" :disabled="!canEditScheduleFields" size="small" /></a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="负责人" required><a-select v-model:value="tf.assignee_id" :options="userOptions" placeholder="选择" allowClear size="small" /></a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="耗时(h)" required><a-input-number v-model:value="tf.est_duration_hours" :min="0.5" :step="0.5" :max="999" :disabled="!canEditScheduleFields" size="small" style="width: 100%" /></a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="切换(h)"><a-input-number v-model:value="tf.switchover_hours" :min="0" :step="0.5" :max="99" :disabled="!canEditScheduleFields" size="small" style="width: 100%" /></a-form-item>
          </a-col>
        </a-row>
        <a-row v-if="!isEditingParent" :gutter="12">
          <a-col :span="12">
            <a-form-item label="前置任务"><a-select v-model:value="tf.predecessor_ids" mode="multiple" :options="leafTaskOptions" placeholder="可多选" allowClear :disabled="!canEditScheduleFields" size="small" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="指定仪器" :required="isInstrumentRequired">
              <a-select v-model:value="tf.instrument_ids" mode="multiple" :options="instrumentOptions" :placeholder="isInstrumentRequired ? '必填：请选择仪器' : '选择仪器'" allowClear :disabled="!canEditScheduleFields" size="small" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
    <PlanInsertPreviewModal
      :open="insertPreviewOpen"
      :confirming="confirmingInsert"
      :result="insertPreview"
      @confirm="handleConfirmInsert"
      @cancel="handleCancelInsert"
    />
    <ApprovalGateModal
      :open="approvalGateOpen"
      :tasks="allTasks"
      :submitting="approvalGateSubmitting"
      @submit="handleCreateApprovalGate"
      @cancel="approvalGateOpen = false"
    />
  </div>
</template>
<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { isAxiosError } from 'axios'
import { PlusOutlined, EditOutlined, LeftOutlined, DeleteOutlined, PlayCircleOutlined, FileTextOutlined, ImportOutlined } from '@ant-design/icons-vue'
import { commitProjectPlanDrafts, createApprovalGate, getProject, getProjectDAG, updateTask, deleteTask, getUsers, getTaskTypes, getInstruments, applyProjectPlan, confirmProjectPlanInsert, type ApprovalGateCreatePayload, type ProjectPlanDraftTaskPayload, type Project, type Task, type DAGData, type TaskTypeConfig } from '@/services/api'
import type { ProjectPlanApplyResult } from '@/types'
import PlanInsertPreviewModal from './components/PlanInsertPreviewModal.vue'
import ApprovalGateModal from './components/ApprovalGateModal.vue'
import dayjs from 'dayjs'
const router = useRouter()
const route = useRoute()
const projectId = Number(route.query.id)
const project = ref<Project | null>(null)
const dagData = ref<DAGData | null>(null)
const allTasks = ref<Task[]>([])
const expandedTaskIds = ref<number[]>([])
const loading = ref(true)
const taskOpen = ref(false)
const editingTask = ref<Task | null>(null)
const insertPreview = ref<ProjectPlanApplyResult | null>(null)
const insertPreviewOpen = ref(false)
const confirmingInsert = ref(false)
const approvalGateOpen = ref(false)
const approvalGateSubmitting = ref(false)
const parentTaskId = ref<number | null>(null)
let nextDraftId = -1
const taskTypeOptions = ref<{ label: string; value: string; resource_type: string }[]>([])
const taskTypeMap = ref<Record<string, TaskTypeConfig>>({})
const REQUIRED_INSTRUMENT_TASK_TYPES = new Set(['FFKF_001', 'FFYZ_001'])
const userOptions = ref<{ label: string; value: number }[]>([])
const instrumentOptions = ref<{ label: string; value: number }[]>([])
const instrumentCodeMap = computed(() => {
  const map: Record<number, string> = {}
  instrumentOptions.value.forEach(instrument => { map[instrument.value] = instrument.label })
  return map
})
const tf = reactive({ name: '', task_type: '', est_duration_hours: 8, switchover_hours: 0.5, predecessor_ids: [] as number[], instrument_ids: [] as number[], assignee_id: null as number | null, parent_id: null as number | null })
const statusLabels: Record<string, string> = { active: '进行中', completed: '已完成', pending: '待启动', suspended: '已暂停', cancelled: '已取消', draft: '草稿' }
function priorityLabel(priority: number) {
  return priority === 1 ? '一级（最高）' : priority === 2 ? '二级' : '三级'
}
function priorityColor(priority: number) {
  if (priority === 1) return '#dc2626'
  if (priority === 2) return '#ea580c'
  return '#2563eb'
}
const capTagOptions = [
  { label: '离子源', value: '离子源' }, { label: '质量分析器', value: '质量分析器' },
  { label: '方法类型', value: '方法类型' }, { label: '灵敏度等级', value: '灵敏度等级' },
]
const capValOpts: Record<string, { label: string; value: string }[]> = {
  '离子源': [{ label: 'ESI', value: 'ESI' }, { label: 'APCI', value: 'APCI' }],
  '质量分析器': [{ label: 'QqQ', value: 'QqQ' }, { label: 'Q-TOF', value: 'Q-TOF' }],
  '方法类型': [{ label: '基因毒杂质', value: '基因毒杂质' }, { label: '有关物质', value: '有关物质' }, { label: '含量测定', value: '含量测定' }],
  '灵敏度等级': [{ label: '痕量', value: '痕量' }, { label: '常量', value: '常量' }],
}
function getCapValueOpts(tagName: string) { return capValOpts[tagName] || [] }
function goBack() { router.push('/projects/ledger') }
function getTaskTypeName(code: string) {
  if (code === 'approval_gate') return '方案签批'
  return taskTypeMap.value[code]?.name || code
}
function taskStatusLabel(status: string) { return ({ pending: '待开始', ready: '可排程', scheduled: '已排程', running: '运行中', done: '已完成', blocked: '已延期', waiting_external: '等待外部签批' } as Record<string, string>)[status] || status }
function gateStatusMeta(status?: string | null) {
  return ({ not_submitted: { label: '待提交', color: 'default' }, waiting_approval: { label: '等待客户', color: 'blue' }, approved: { label: '已签批', color: 'green' } } as Record<string, { label: string; color: string }>)[status || 'not_submitted']
}
function gateDateText(task: Task) {
  if (task.approved_at) return `签批 ${dayjs(task.approved_at).format('MM-DD HH:mm')}`
  if (task.expected_approval_at) return `预计 ${dayjs(task.expected_approval_at).format('MM-DD HH:mm')}`
  return '尚未提交客户'
}
function getTaskTypeColor(code: string) {
      const m: Record<string, string> = { FFKF_001: '#8b5cf6', QCFA_001: '#f59e0b', FFYZ_001: '#10b981', SJCL_001: '#3b82f6', ZXBG_001: '#ef4444' }
  return m[code] || '#94a3b8'
}
function getTaskNameById(id: number) {
  const t = allTasks.value.find(t => t.id === id)
  return t ? (t.name.length > 8 ? t.name.slice(0, 8) + '...' : t.name) : '#' + id
}
function getAssigneeName(id: number | null | undefined) {
  if (!id) return null
  return userOptions.value.find(u => u.value === id)?.label || null
}
function getInstrumentCode(id: number) {
  return instrumentCodeMap.value[id] || `ID ${id}`
}
function getTaskInstrumentIds(task: Task): number[] {
  if (!task.children || task.children.length === 0) return task.instrument_ids || []
  const ids = task.children.flatMap(child => getTaskInstrumentIds(child))
  return Array.from(new Set(ids))
}
function getInstrumentSummary(task: Task) {
  return getTaskInstrumentIds(task).map(getInstrumentCode).join('、')
}
function buildTree(tasks: Task[]): Task[] {
  const map = new Map<number, Task>()
  const roots: Task[] = []
  tasks.forEach(t => { map.set(t.id, { ...t, children: [] }) })
  tasks.forEach(t => {
    const node = map.get(t.id)!
    if (t.parent_id && map.has(t.parent_id)) {
      const parent = map.get(t.parent_id)!
      if (!parent.children) parent.children = []
      parent.children!.push(node)
    } else { roots.push(node) }
  })
  return roots
}
const treeTasks = computed(() => buildTree(allTasks.value))
const flatTaskCount = computed(() => allTasks.value.length)
function countLeaves(nodes: Task[]): number {
  let count = 0
  for (const n of nodes) {
    if (!n.children || n.children.length === 0) count++
    else count += countLeaves(n.children)
  }
  return count
}
const leafTaskCount = computed(() => countLeaves(treeTasks.value))
function sumChildrenHours(task: Task): number {
  if (!task.children || task.children.length === 0) return task.est_duration_hours || 0
  return task.children.reduce((s, c) => s + sumChildrenHours(c), 0)
}
function isParentTask(id: number): boolean { return allTasks.value.some(t => t.parent_id === id) }
function getParentTaskIds(tasks: Task[]): number[] {
  return [...new Set(tasks.flatMap(task => task.parent_id == null ? [] : [task.parent_id]))]
}
function expandTask(taskId: number | null) {
  if (taskId != null && !expandedTaskIds.value.includes(taskId)) {
    expandedTaskIds.value = [...expandedTaskIds.value, taskId]
  }
}
const isEditingParent = computed(() => editingTask.value ? isParentTask(editingTask.value.id) : false)
const canEditScheduleFields = computed(() => editingTask.value?.can_edit_schedule_fields !== false)
const isInstrumentRequired = computed(() => REQUIRED_INSTRUMENT_TASK_TYPES.has(tf.task_type))
const hasLocalDrafts = computed(() => allTasks.value.some(task => task.is_local_draft))
const hasPendingPlanChanges = computed(() => allTasks.value.some(task =>
  !task.children?.length
  && (task.schedule_dirty || ['pending', 'ready'].includes(task.status)),
))
const parentTaskOptions = computed(() => allTasks.value.filter(t => !editingTask.value || t.id !== editingTask.value.id).map(t => ({ label: t.name, value: t.id })))
const leafTaskOptions = computed(() => allTasks.value.filter(t => !t.children || t.children.length === 0).map(t => ({ label: t.name, value: t.id })))
async function fetchProject() {
  loading.value = true
  try {
    const [p, d] = await Promise.all([getProject(projectId), getProjectDAG(projectId)])
    project.value = p; dagData.value = d; allTasks.value = p.tasks || []
    expandedTaskIds.value = getParentTaskIds(allTasks.value)
  } catch { message.error('加载项目失败') }
  finally { loading.value = false }
}
function openAddTask(parentId: number | null) {
  editingTask.value = null; parentTaskId.value = parentId
  Object.assign(tf, { name: '', task_type: taskTypeOptions.value[0]?.value || '', est_duration_hours: 8, switchover_hours: 0.5, predecessor_ids: [], instrument_ids: [], assignee_id: null, parent_id: parentId })
  taskOpen.value = true
}
function openEditTask(t: Task) {
  if (hasLocalDrafts.value && !t.is_local_draft) {
    message.warning('请先保存当前新增草稿，再编辑数据库中的任务')
    return
  }
  editingTask.value = t; parentTaskId.value = null
  Object.assign(tf, { name: t.name, task_type: t.task_type, est_duration_hours: t.est_duration_hours || 8, switchover_hours: t.switchover_hours, predecessor_ids: t.predecessor_ids || [], instrument_ids: t.instrument_ids || [], assignee_id: t.assignee_id || null, parent_id: t.parent_id || null })
  taskOpen.value = true
}
async function handleTaskSubmit() {
  if (!project.value) return
  if (!tf.name) { message.error('请输入任务名称'); return }
  const isParent = isEditingParent.value
  if (!isParent) {
    if (!tf.task_type) { message.error('请选择任务类型'); return }
    if (!tf.assignee_id) { message.error('请选择负责人'); return }
    if (!tf.est_duration_hours || tf.est_duration_hours <= 0) { message.error('请输入预计耗时'); return }
    if (isInstrumentRequired.value && !tf.instrument_ids.length) { message.error('方法开发和方法验证必须指定仪器'); return }
  }
  const payload = {
    name: tf.name, task_type: isParent ? 'group' : tf.task_type,
    requires_instrument: isParent ? false : (taskTypeMap.value[tf.task_type]?.resource_type || 'both') !== 'human',
    est_duration_hours: isParent ? null : tf.est_duration_hours, switchover_hours: isParent ? 0 : tf.switchover_hours,
    predecessor_ids: isParent ? [] : tf.predecessor_ids, assignee_id: isParent ? null : (tf.assignee_id || null),
    parent_id: tf.parent_id, instrument_ids: isParent ? [] : tf.instrument_ids,
  }
  try {
    if (editingTask.value?.is_local_draft) {
      const index = allTasks.value.findIndex(task => task.id === editingTask.value?.id)
      if (index >= 0) allTasks.value[index] = buildDraftTask(payload, editingTask.value.id)
      expandTask(payload.parent_id)
      message.success('草稿任务已更新')
    } else if (editingTask.value) {
      await updateTask(editingTask.value.id, payload)
      message.success('任务更新成功')
      await fetchProject()
    } else {
      allTasks.value.push(buildDraftTask(payload, nextDraftId--))
      expandTask(payload.parent_id)
      message.success('任务已加入本地草稿，保存前不会写入数据库')
    }
    taskOpen.value = false; editingTask.value = null
  } catch (error: unknown) { message.error(errorDetail(error, '操作失败')) }
}
async function handleDeleteTask(taskId: number) {
  const task = allTasks.value.find(item => item.id === taskId)
  if (task?.is_local_draft) {
    const removedIds = new Set<number>([taskId])
    let changed = true
    while (changed) {
      changed = false
      for (const candidate of allTasks.value) {
        if (candidate.parent_id && removedIds.has(candidate.parent_id) && !removedIds.has(candidate.id)) {
          removedIds.add(candidate.id)
          changed = true
        }
      }
    }
    allTasks.value = allTasks.value
      .filter(candidate => !removedIds.has(candidate.id))
      .map(candidate => ({
        ...candidate,
        predecessor_ids: candidate.predecessor_ids.filter(id => !removedIds.has(id)),
      }))
    message.success('未保存草稿已删除')
    return
  }
  if (hasLocalDrafts.value) { message.warning('请先保存当前新增草稿，再删除数据库中的任务'); return }
  try { await deleteTask(taskId); message.success(task?.is_external_gate ? '方案签批已删除' : '任务已删除'); await fetchProject() }
  catch { message.error('删除失败') }
}
function buildDraftTask(
  payload: {
    name: string; task_type: string; requires_instrument: boolean;
    est_duration_hours: number | null; switchover_hours: number;
    predecessor_ids: number[]; assignee_id: number | null;
    parent_id: number | null; instrument_ids: number[];
  },
  id: number,
): Task {
  return {
    id,
    project_id: projectId,
    name: payload.name,
    task_type: payload.task_type,
    requires_instrument: payload.requires_instrument,
    requires_human: payload.task_type !== 'group',
    est_duration_hours: payload.est_duration_hours ?? undefined,
    switchover_hours: payload.switchover_hours,
    status: 'pending',
    schedule_dirty: true,
    schedule_lock_status: 'none',
    can_edit_schedule_fields: true,
    priority_weight: 1,
    allow_split: false,
    instrument_ids: [...payload.instrument_ids],
    predecessor_ids: [...payload.predecessor_ids],
    assignee_id: payload.assignee_id,
    assignee_name: getAssigneeName(payload.assignee_id),
    parent_id: payload.parent_id,
    is_local_draft: true,
  }
}
async function handleCreateApprovalGate(payload: ApprovalGateCreatePayload) {
  approvalGateSubmitting.value = true
  try {
    await createApprovalGate(projectId, payload)
    approvalGateOpen.value = false
    message.success('方案签批已添加，后续任务已转为等待签批')
    await fetchProject()
  } catch (error: unknown) { message.error(errorDetail(error, '添加方案签批失败')) }
  finally { approvalGateSubmitting.value = false }
}
function openApprovalGate() {
  if (hasLocalDrafts.value) {
    message.warning('请先保存当前新增草稿，再添加独立方案签批')
    return
  }
  approvalGateOpen.value = true
}
function openTemplateImport() {
  if (!project.value) return
  if (allTasks.value.length) {
    Modal.warning({ title: '当前项目已有计划', content: '模板计划只能导入到尚未创建任何任务的空项目，避免重复或覆盖现有计划。' })
    return
  }
  if (!project.value?.estimated_hours) { message.error('请先填写项目预计工时'); return }
  if (!project.value.manager_id) { message.error('请先设置项目负责人'); return }
  const [methodHours, schemeHours, validationHours, reportHours] = allocateTemplateHours(project.value.estimated_hours)
  const managerId = project.value.manager_id
  const method = buildDraftTask(templatePayload('方法开发', 'FFKF_001', true, methodHours, [], managerId), nextDraftId--)
  const scheme = buildDraftTask(templatePayload('方案撰写', 'QCFA_001', false, schemeHours, [method.id], managerId), nextDraftId--)
  const restrictionId = nextDraftId--
  const validation = buildDraftTask(templatePayload('方法验证', 'FFYZ_001', true, validationHours, [restrictionId], managerId), nextDraftId--)
  const report = buildDraftTask(templatePayload('报告撰写', 'ZXBG_001', false, reportHours, [validation.id], managerId), nextDraftId--)
  validation.status = 'waiting_external'; validation.schedule_dirty = false
  report.status = 'waiting_external'; report.schedule_dirty = false
  const restriction: Task = {
    id: restrictionId, project_id: projectId, name: '方案签批', task_type: 'approval_gate',
    requires_instrument: false, requires_human: false, switchover_hours: 0,
    status: 'waiting_external', schedule_dirty: false, schedule_lock_status: 'none',
    can_edit_schedule_fields: true, priority_weight: 1, allow_split: false,
    instrument_ids: [], predecessor_ids: [scheme.id], assignee_id: null,
    assignee_name: null, parent_id: null, is_external_gate: true,
    gate_status: 'not_submitted', is_local_draft: true,
  }
  allTasks.value = [method, scheme, restriction, validation, report]
  message.success('模板计划已导入当前页面，点击保存前不会写入数据库')
}
function templatePayload(name: string, taskType: string, requiresInstrument: boolean, hours: number, predecessorIds: number[], assigneeId: number) {
  return { name, task_type: taskType, requires_instrument: requiresInstrument, est_duration_hours: hours, switchover_hours: 0, predecessor_ids: predecessorIds, assignee_id: assigneeId, parent_id: null, instrument_ids: [] }
}
function allocateTemplateHours(total: number): [number, number, number, number] {
  const first = [0.7, 0.05, 0.2].map(rate => Math.round(total * rate * 100) / 100)
  return [first[0], first[1], first[2], Math.round((total - first.reduce((sum, value) => sum + value, 0)) * 100) / 100]
}
async function loadInstruments() {
  try {
    const insts = await getInstruments({ include_unavailable: true })
    instrumentOptions.value = insts.map(i => ({ label: i.code, value: i.id }))
  } catch (e) { console.error("loadInstruments failed:", e) }
}
async function loadUsers() {
  try { const users = await getUsers(); userOptions.value = users.filter(u => u.is_active).map(u => ({ label: u.display_name, value: u.id })) }
  catch { console.error('loadUsers failed') }
}
async function loadTaskTypes() {
  try {
    const types = await getTaskTypes(); const active = types.filter(t => t.is_active && t.code !== 'approval_gate')
    taskTypeOptions.value = active.map(t => ({ label: t.name, value: t.code, resource_type: t.resource_type }))
    taskTypeMap.value = {}; active.forEach(t => { taskTypeMap.value[t.code] = t })
  } catch { console.error('loadTaskTypes failed') }
}
const scheduling = ref(false)
async function handleStartSchedule() {
  const missingInstrumentTasks = allTasks.value.filter(task => (
    !isParentTask(task.id)
    && !task.is_external_gate
    && REQUIRED_INSTRUMENT_TASK_TYPES.has(task.task_type)
    && !task.instrument_ids.length
  ))
  if (missingInstrumentTasks.length) {
    message.error(`请先为任务【${missingInstrumentTasks.map(task => task.name).join('、')}】指定仪器`)
    return
  }
  scheduling.value = true
  try {
    const drafts = allTasks.value.filter(task => task.is_local_draft)
    if (drafts.length) {
      const saveResult = await commitProjectPlanDrafts(projectId, drafts.map(toDraftPayload))
      message.success(saveResult.message)
      await fetchProject()
    }
    const result = await applyProjectPlan(projectId)
    if (result.status === 'applied') {
      message.success(result.message || '排程完成')
      await fetchProject()
    } else if (result.status === 'no_changes') {
      message.info(result.message || '当前没有需要重新排程的任务')
    } else if (result.status === 'insert_confirmation_required') {
      insertPreview.value = result
      insertPreviewOpen.value = true
    } else {
      Modal.error({ title: '排程失败', content: result.message || '当前计划无法在已有排程中安排。' })
    }
  } catch (error: unknown) {
    Modal.error({ title: '排程请求失败', content: errorDetail(error, '服务器内部错误，请稍后重试。') })
  } finally { scheduling.value = false }
}
function toDraftPayload(task: Task): ProjectPlanDraftTaskPayload {
  const isParent = isParentTask(task.id)
  return {
    client_id: task.id,
    name: task.name,
    task_type: isParent ? 'group' : task.task_type,
    requires_instrument: isParent ? false : task.requires_instrument,
    requires_human: isParent ? false : task.requires_human,
    estimated_hours: isParent ? null : (task.est_duration_hours ?? null),
    switchover_hours: isParent ? 0 : task.switchover_hours,
    assignee_id: isParent ? null : task.assignee_id,
    parent_id: task.parent_id,
    predecessor_ids: isParent ? [] : [...task.predecessor_ids],
    instrument_ids: isParent ? [] : [...task.instrument_ids],
    is_external_gate: Boolean(task.is_external_gate),
  }
}
async function handleConfirmInsert() {
  const previewToken = insertPreview.value?.preview_token
  if (!previewToken) return
  confirmingInsert.value = true
  try {
    const result = await confirmProjectPlanInsert(projectId, previewToken)
    message.success(result.message || '插单排程完成')
    insertPreviewOpen.value = false
    insertPreview.value = null
    await fetchProject()
  } catch (error: unknown) {
    message.error(errorDetail(error, '插单确认失败，请重新计算影响'))
  } finally { confirmingInsert.value = false }
}
function handleCancelInsert() {
  insertPreviewOpen.value = false
  insertPreview.value = null
}
function errorDetail(error: unknown, fallback: string) {
  if (isAxiosError<{ detail?: string }>(error)) return error.response?.data?.detail || fallback
  return fallback
}
onMounted(async () => {
  if (!projectId) { message.error('缺少项目ID'); router.push('/projects/ledger'); return }
  await loadTaskTypes(); await Promise.all([fetchProject(), loadUsers(), loadInstruments()])
})
</script>
<style scoped>
.project-info { margin-bottom: 16px; }
.instrument-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.instrument-tag {
  margin: 0;
  white-space: nowrap;
}
</style>
