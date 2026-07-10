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
          <a-descriptions-item label="优先级"><a-tag :color="project.priority >= 5 ? '#dc2626' : project.priority >= 3 ? '#ea580c' : '#2563eb'">{{ project.priority }}</a-tag></a-descriptions-item>
          <a-descriptions-item label="开始日期">{{ project.start_date ? dayjs(project.start_date).format('YYYY-MM-DD') : '-' }}</a-descriptions-item>
          <a-descriptions-item label="结题日期">{{ project.end_date ? dayjs(project.end_date).format('YYYY-MM-DD') : '-' }}</a-descriptions-item>
          <a-descriptions-item label="SLA">{{ slaLabels[project.sla_level || 'standard'] }}</a-descriptions-item>
          <a-descriptions-item label="利润权重">{{ project.profit_weight }}</a-descriptions-item>
        </a-descriptions>
      </div>
      <div class="action-bar">
        <a-button type="primary" @click="openAddTask(null)"><PlusOutlined /> 添加顶级任务</a-button>
        <span style="margin-left: 8px; font-size: 12px; color: #94a3b8">点击左侧 &gt; 展开/收起子任务</span>
        <span style="margin-left: auto; font-size: 12px; color: #94a3b8">{{ flatTaskCount }} 个任务（{{ leafTaskCount }} 个叶子任务）</span>
      </div>
      <a-table :dataSource="treeTasks" rowKey="id" size="small" :pagination="{ pageSize: 50, showSizeChanger: true }"
        :defaultExpandAllRows="true" :indentSize="24">
        <a-table-column title="任务名称" dataIndex="name" key="name">
          <template #default="{ record }">
            <span :style="{ fontWeight: record.children?.length ? 600 : 400 }">{{ record.name }}</span>
            
          </template>
        </a-table-column>
        <a-table-column title="类型" key="task_type" width="120">
          <template #default="{ record }">
            <a-tag v-if="!record.children?.length" :color="getTaskTypeColor(record.task_type)" style="font-size: 11px">{{ getTaskTypeName(record.task_type) }}</a-tag>
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
            <a-space :size="0">
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
            <a-form-item label="父任务"><a-select v-model:value="tf.parent_id" :options="parentTaskOptions" placeholder="顶级任务" allowClear :disabled="!!parentTaskId" size="small" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="任务名称" required><a-input v-model:value="tf.name" placeholder="输入名称" size="small" /></a-form-item>
          </a-col>
        </a-row>
        <a-row v-if="!isEditingParent" :gutter="12">
          <a-col :span="6">
            <a-form-item label="任务类型" required><a-select v-model:value="tf.task_type" :options="taskTypeOptions" placeholder="选择" size="small" /></a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="负责人" required><a-select v-model:value="tf.assignee_id" :options="userOptions" placeholder="选择" allowClear size="small" /></a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="耗时(h)" required><a-input-number v-model:value="tf.est_duration_hours" :min="0.5" :step="0.5" :max="999" size="small" style="width: 100%" /></a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item label="切换(h)"><a-input-number v-model:value="tf.switchover_hours" :min="0" :step="0.5" :max="99" size="small" style="width: 100%" /></a-form-item>
          </a-col>
        </a-row>
        <a-row v-if="!isEditingParent" :gutter="12">
          <a-col :span="12">
            <a-form-item label="前置任务"><a-select v-model:value="tf.predecessor_ids" mode="multiple" :options="leafTaskOptions" placeholder="可多选" allowClear size="small" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="指定仪器">
              <a-select v-model:value="tf.instrument_ids" mode="multiple" :options="instrumentOptions" placeholder="选择仪器" allowClear size="small" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, LeftOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import { getProject, getProjectDAG, addTask, updateTask, deleteTask, getUsers, getTaskTypes, getInstruments, generateSchedule, type Project, type Task, type DAGData, type TaskTypeConfig } from '@/services/api'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()
const projectId = Number(route.query.id)
const project = ref<Project | null>(null)
const dagData = ref<DAGData | null>(null)
const allTasks = ref<Task[]>([])
const loading = ref(true)
const taskOpen = ref(false)
const editingTask = ref<Task | null>(null)
const parentTaskId = ref<number | null>(null)
const taskTypeOptions = ref<{ label: string; value: string; resource_type: string }[]>([])
const taskTypeMap = ref<Record<string, TaskTypeConfig>>({})
const userOptions = ref<{ label: string; value: number }[]>([])
const instrumentOptions = ref<{ label: string; value: number }[]>([])
const instrumentCodeMap = computed(() => {
  const map: Record<number, string> = {}
  instrumentOptions.value.forEach(instrument => { map[instrument.value] = instrument.label })
  return map
})

const tf = reactive({ name: '', task_type: '', est_duration_hours: 8, switchover_hours: 0.5, predecessor_ids: [] as number[], instrument_ids: [] as number[], assignee_id: null as number | null, parent_id: null as number | null })

const statusLabels: Record<string, string> = { active: '进行中', completed: '已完成', pending: '待启动', suspended: '已暂停', cancelled: '已取消', draft: '草稿' }
const slaLabels: Record<string, string> = { standard: '标准', expedited: '加急', rush: '特急' }

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

function getTaskTypeName(code: string) { return taskTypeMap.value[code]?.name || code }
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
const isEditingParent = computed(() => editingTask.value ? isParentTask(editingTask.value.id) : false)

const parentTaskOptions = computed(() => allTasks.value.filter(t => !editingTask.value || t.id !== editingTask.value.id).map(t => ({ label: t.name, value: t.id })))
const leafTaskOptions = computed(() => allTasks.value.filter(t => !t.children || t.children.length === 0).map(t => ({ label: t.name, value: t.id })))

async function fetchProject() {
  loading.value = true
  try {
    const [p, d] = await Promise.all([getProject(projectId), getProjectDAG(projectId)])
    project.value = p; dagData.value = d; allTasks.value = p.tasks || []
  } catch { message.error('加载项目失败') }
  finally { loading.value = false }
}

function openAddTask(parentId: number | null) {
  editingTask.value = null; parentTaskId.value = parentId
  Object.assign(tf, { name: '', task_type: taskTypeOptions.value[0]?.value || '', est_duration_hours: 8, switchover_hours: 0.5, predecessor_ids: [], instrument_ids: [], assignee_id: null, parent_id: parentId })
  taskOpen.value = true
}

function openEditTask(t: Task) {
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
  }
  const payload = {
    name: tf.name, task_type: isParent ? 'group' : tf.task_type,
    requires_instrument: isParent ? false : (taskTypeMap.value[tf.task_type]?.resource_type || 'both') !== 'human',
    est_duration_hours: isParent ? null : tf.est_duration_hours, switchover_hours: isParent ? 0 : tf.switchover_hours,
    predecessor_ids: isParent ? [] : tf.predecessor_ids, assignee_id: isParent ? null : (tf.assignee_id || null),
    parent_id: tf.parent_id, instrument_ids: isParent ? [] : tf.instrument_ids,
  }
  try {
    if (editingTask.value) { await updateTask(editingTask.value.id, payload as any); message.success('任务更新成功') }
    else { await addTask(project.value.id, payload as any); message.success('任务添加成功') }
    taskOpen.value = false; editingTask.value = null
    await fetchProject()
  } catch { message.error('操作失败') }
}

async function handleDeleteTask(taskId: number) {
  try { await deleteTask(taskId); message.success('任务已删除'); await fetchProject() }
  catch { message.error('删除失败') }
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
    const types = await getTaskTypes(); const active = types.filter(t => t.is_active)
    taskTypeOptions.value = active.map(t => ({ label: t.name, value: t.code, resource_type: t.resource_type }))
    taskTypeMap.value = {}; active.forEach(t => { taskTypeMap.value[t.code] = t })
  } catch { console.error('loadTaskTypes failed') }
}

const scheduling = ref(false)

async function handleStartSchedule() {
  scheduling.value = true
  try {
    const r = await generateSchedule()
    if (r.status === 'ok') message.success(r.message || '排程完成')
    else Modal.error({ title: '排程失败', content: r.message || '请检查任务、仪器和项目时间配置。' })
  } catch { Modal.error({ title: '排程请求失败', content: '服务器内部错误，请稍后重试。' }) }
  finally { scheduling.value = false }
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
