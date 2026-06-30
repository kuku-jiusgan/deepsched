<template>
  <div>
    <div class="page-header"><h2>项目看板</h2><p>管理项目、任务与依赖关系</p></div>
    <div class="action-bar">
      <a-button type="primary" @click="openCreate"><PlusOutlined /> 新建项目</a-button>
      <a-input placeholder="项目编号" allowClear style="width: 150px" v-model:value="filterCode"><template #prefix><SearchOutlined /></template></a-input>
      <a-input placeholder="项目名称" allowClear style="width: 180px" v-model:value="filterName"><template #prefix><SearchOutlined /></template></a-input>
      <a-input placeholder="客户名称" allowClear style="width: 150px" v-model:value="filterClient"><template #prefix><SearchOutlined /></template></a-input>
      <a-range-picker :placeholder="['开始日期','结束日期']" style="width: 240px" v-model:value="filterDateRange" allowClear />
      <span style="margin-left: auto; font-size: 12px; color: #94a3b8; align-self: center">{{ filtered.length }} / {{ projects.length }} 个项目</span>
    </div>
    <a-spin v-if="loading" size="large" style="display: block; margin: 50px auto" />
    <a-table v-else :dataSource="filtered" :columns="columns" rowKey="id" size="small" />
    <a-modal title="新建项目" v-model:open="createOpen" @ok="handleCreate" width="640" okText="创建项目">
      <a-form layout="vertical">
        <a-form-item label="项目名称" required><a-input v-model:value="cf.name" placeholder="如：某注射剂基因毒杂质研究" /></a-form-item>
        <a-form-item label="项目编号" required><a-input v-model:value="cf.code" placeholder="如：GT-2026-001" /></a-form-item>
        <a-form-item label="客户名称"><a-input v-model:value="cf.client_name" placeholder="如：某制药公司" /></a-form-item>
        <a-form-item label="项目负责人"><a-input v-model:value="cf.manager" placeholder="如：张三" /></a-form-item>
        <a-space :size="16">
          <a-form-item label="优先级"><a-input-number v-model:value="cf.priority" :min="1" :max="10" /></a-form-item>
          <a-form-item label="SLA等级"><a-select v-model:value="cf.sla_level" style="width: 120px" :options="slaOptions" /></a-form-item>
          <a-form-item label="利润权重"><a-input-number v-model:value="cf.profit_weight" :min="0.5" :max="3" :step="0.1" /></a-form-item>
        </a-space>
        <a-space :size="16" style="width: 100%">
          <a-form-item label="项目开始日期" style="width: 200px"><a-date-picker v-model:value="cf.start_date" style="width: 100%" /></a-form-item>
          <a-form-item label="项目结题日期" style="width: 200px"><a-date-picker v-model:value="cf.end_date" style="width: 100%" /></a-form-item>
        </a-space>
      </a-form>
    </a-modal>
    <a-modal title="编辑项目" v-model:open="editOpen" @ok="handleUpdateProject" width="640" okText="保存">
      <a-form layout="vertical">
        <a-form-item label="项目名称" required><a-input v-model:value="ef.name" /></a-form-item>
        <a-form-item label="项目编号" required><a-input v-model:value="ef.code" /></a-form-item>
        <a-form-item label="客户名称"><a-input v-model:value="ef.client_name" /></a-form-item>
        <a-form-item label="项目负责人"><a-input v-model:value="ef.manager" /></a-form-item>
        <a-space :size="16">
          <a-form-item label="优先级"><a-input-number v-model:value="ef.priority" :min="1" :max="10" /></a-form-item>
          <a-form-item label="SLA等级"><a-select v-model:value="ef.sla_level" style="width: 120px" :options="slaOptions" /></a-form-item>
          <a-form-item label="利润权重"><a-input-number v-model:value="ef.profit_weight" :min="0.5" :max="3" :step="0.1" /></a-form-item>
        </a-space>
        <a-space :size="16" style="width: 100%">
          <a-form-item label="项目开始日期" style="width: 200px"><a-date-picker v-model:value="ef.start_date" style="width: 100%" /></a-form-item>
          <a-form-item label="项目结题日期" style="width: 200px"><a-date-picker v-model:value="ef.end_date" style="width: 100%" /></a-form-item>
        </a-space>
      </a-form>
    </a-modal>
    <a-drawer :title="selectedProject?.name || '项目详情'" v-model:open="detailOpen" width="720">
      <template #extra><a-button @click="openEditProject"><EditOutlined /> 编辑项目</a-button></template>
      <a-tabs v-if="selectedProject" defaultActiveKey="tasks">
        <a-tab-pane key="tasks" tab="任务列表">
          <div style="margin-bottom: 12px"><a-button type="primary" size="small" @click="openAddTask"><PlusOutlined /> 添加任务</a-button></div>
          <a-table :dataSource="selectedProject.tasks || []" rowKey="id" size="small" :pagination="false">
            <a-table-column title="任务名称" dataIndex="name" key="name" />
            <a-table-column title="类型" dataIndex="task_type" key="type" width="90" />
            <a-table-column title="预计耗时(h)" dataIndex="est_duration_hours" key="dur" width="100" />
            <a-table-column title="状态" dataIndex="status" key="status" width="90" />
            <a-table-column title="操作" key="actions" width="60">
              <template #default="{ record }"><a-button type="link" size="small" @click="openEditTask(record)"><EditOutlined /></a-button></template>
            </a-table-column>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="dag" tab="依赖关系">
          <div v-if="dagData">
            <div style="font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 8px">任务节点 ({{ dagData.nodes.length }})</div>
            <a-tag v-for="n in dagData.nodes" :key="n.id" :color="n.requires_instrument ? '#2563eb' : '#94a3b8'" style="margin: 4px">{{ n.name }} ({{ n.type }})</a-tag>
            <div v-if="dagData.edges.length" style="margin-top: 16px">
              <strong style="color: #334155; font-size: 13px">依赖关系：</strong>
              <div v-for="(e,i) in dagData.edges" :key="i" style="font-size: 12px; color: #64748b; margin-top: 4px">任务{{ e.from }} -> 任务{{ e.to }}</div>
            </div>
          </div>
          <a-spin v-else />
        </a-tab-pane>
      </a-tabs>
    </a-drawer>
    <a-modal :title="editingTask ? '编辑任务' : '添加任务'" v-model:open="taskOpen" @ok="handleTaskSubmit" width="600" :okText="editingTask ? '保存' : '添加任务'">
      <a-form layout="vertical">
        <a-form-item label="任务名称" required><a-input v-model:value="tf.name" placeholder="如：LC-MS方法开发" /></a-form-item>
        <a-space :size="16" style="width: 100%">
          <a-form-item label="任务类型"><a-select v-model:value="tf.task_type" style="width: 140px" :options="[{label:'仪器依赖型',value:'instrument'},{label:'人工型',value:'manual'},{label:'等待型',value:'waiting'}]" /></a-form-item>
          <a-form-item label="预计耗时(小时)" required><a-input-number v-model:value="tf.est_duration_hours" :min="0.5" :step="0.5" style="width: 120px" /></a-form-item>
          <a-form-item label="切换时间(h)"><a-input-number v-model:value="tf.switchover_hours" :min="0" :step="0.5" style="width: 100px" /></a-form-item>
        </a-space>
        <a-form-item label="前置依赖任务">
          <a-select mode="multiple" v-model:value="tf.predecessor_ids" placeholder="选择依赖的前置任务（可选）"
            :options="(selectedProject?.tasks || []).map(t => ({ label: t.name + ' (' + t.task_type + ')', value: t.id }))" />
        </a-form-item>
        <a-divider>仪器能力要求（仅仪器任务需要）</a-divider>
        <a-space v-for="(cap, idx) in tf.capability_requirements" :key="idx" style="display: flex; margin-bottom: 8px" align="baseline">
          <a-select v-model:value="cap.tag_name" placeholder="能力标签" style="width: 140px" :options="[{label:'离子源',value:'离子源'},{label:'质量分析器',value:'质量分析器'},{label:'方法类型',value:'方法类型'},{label:'灵敏度等级',value:'灵敏度等级'}]" />
          <a-select v-model:value="cap.tag_value" placeholder="标签值" style="width: 160px" :options="(capValOpts as any)[cap.tag_name] || []" />
          <a-button type="text" danger @click="tf.capability_requirements.splice(idx, 1)"><DeleteOutlined /></a-button>
        </a-space>
        <a-button type="dashed" block @click="tf.capability_requirements.push({ tag_name: '', tag_value: '' })"><PlusOutlined /> 添加能力要求</a-button>
      </a-form>
    </a-modal>
  </div>
</template>


<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, SearchOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { getProjects, createProject, updateProject, getProject, getProjectDAG, addTask, updateTask } from '@/services/api'
import type { Project, DAGData, Task } from '@/types'
import dayjs from 'dayjs'

const projects = ref<Project[]>([])
const loading = ref(true)
const createOpen = ref(false)
const editOpen = ref(false)
const detailOpen = ref(false)
const taskOpen = ref(false)
const selectedProject = ref<Project | null>(null)
const editingTask = ref<Task | null>(null)
const dagData = ref<DAGData | null>(null)
const filterCode = ref('')
const filterName = ref('')
const filterClient = ref('')
const filterDateRange = ref<any>(null)

const cf = reactive({ name: '', code: '', client_name: '', manager: '', priority: 3, sla_level: 'standard', profit_weight: 1.0, start_date: null as any, end_date: null as any })
const ef = reactive({ name: '', code: '', client_name: '', manager: '', priority: 3, sla_level: 'standard', profit_weight: 1.0, start_date: null as any, end_date: null as any })
const tf = reactive({ name: '', task_type: 'instrument', est_duration_hours: 8, switchover_hours: 0.5, predecessor_ids: [] as number[], capability_requirements: [] as { tag_name: string; tag_value: string }[] })

const slaOptions = [{ label: '标准', value: 'standard' }, { label: '加急', value: 'expedited' }, { label: '特急', value: 'rush' }]
const capValOpts: Record<string, { label: string; value: string }[]> = {
  '离子源': [{ label: 'ESI', value: 'ESI' }, { label: 'APCI', value: 'APCI' }],
  '质量分析器': [{ label: 'QqQ', value: 'QqQ' }, { label: 'Q-TOF', value: 'Q-TOF' }],
  '方法类型': [{ label: '基因毒杂质', value: '基因毒杂质' }, { label: '有关物质', value: '有关物质' }, { label: '含量测定', value: '含量测定' }],
  '灵敏度等级': [{ label: '痕量', value: '痕量' }, { label: '常量', value: '常量' }],
}

const filtered = computed(() => projects.value.filter(p => {
  if (filterCode.value && !p.code.toLowerCase().includes(filterCode.value.toLowerCase())) return false
  if (filterName.value && !p.name.toLowerCase().includes(filterName.value.toLowerCase())) return false
  if (filterClient.value && !(p.client_name || '').toLowerCase().includes(filterClient.value.toLowerCase())) return false
  if (filterDateRange.value?.[0] && filterDateRange.value?.[1] && p.start_date) {
    const d = dayjs(p.start_date)
    if (d.isBefore(filterDateRange.value[0]) || d.isAfter(filterDateRange.value[1])) return false
  }
  return true
}))

const columns = [
  { title: '项目编号', dataIndex: 'code', key: 'code', width: 130 },
  { title: '项目名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '客户', dataIndex: 'client_name', key: 'client', width: 140 },
  { title: '负责人', dataIndex: 'manager', key: 'manager', width: 90 },
  { title: '计划开始', dataIndex: 'start_date', key: 'start', width: 110 },
  { title: '计划完成', dataIndex: 'end_date', key: 'end', width: 110 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', key: 'actions', width: 130 },
]

async function fetchProjects() { loading.value = true; try { projects.value = await getProjects() } catch { message.error('加载项目失败') } finally { loading.value = false } }

function openCreate() { Object.assign(cf, { name: '', code: '', client_name: '', manager: '', priority: 3, sla_level: 'standard', profit_weight: 1.0, start_date: null, end_date: null }); createOpen.value = true }

async function handleCreate() {
  try {
    await createProject({ ...cf, start_date: cf.start_date ? dayjs(cf.start_date).toISOString() : undefined, end_date: cf.end_date ? dayjs(cf.end_date).toISOString() : undefined } as any)
    message.success('项目创建成功'); createOpen.value = false; fetchProjects()
  } catch { message.error('创建失败') }
}

async function handleUpdateProject() {
  if (!selectedProject.value) return
  try {
    await updateProject(selectedProject.value.id, { ...ef, start_date: ef.start_date ? dayjs(ef.start_date).toISOString() : undefined, end_date: ef.end_date ? dayjs(ef.end_date).toISOString() : undefined } as any)
    message.success('项目更新成功'); editOpen.value = false; fetchProjects()
  } catch { message.error('更新失败') }
}

async function handleViewDetail(id: number) {
  try {
    const [p, d] = await Promise.all([getProject(id), getProjectDAG(id)])
    selectedProject.value = p; dagData.value = d; detailOpen.value = true
  } catch { message.error('加载失败') }
}

function openEditProject() {
  if (!selectedProject.value) return
  const p = selectedProject.value
  Object.assign(ef, { name: p.name, code: p.code, client_name: p.client_name || '', manager: p.manager || '', priority: p.priority, sla_level: p.sla_level || 'standard', profit_weight: p.profit_weight, start_date: p.start_date ? dayjs(p.start_date) : null, end_date: p.end_date ? dayjs(p.end_date) : null })
  editOpen.value = true
}

function openAddTask() { editingTask.value = null; Object.assign(tf, { name: '', task_type: 'instrument', est_duration_hours: 8, switchover_hours: 0.5, predecessor_ids: [], capability_requirements: [] }); taskOpen.value = true }

function openEditTask(t: Task) {
  editingTask.value = t
  Object.assign(tf, { name: t.name, task_type: t.task_type, est_duration_hours: t.est_duration_hours || 8, switchover_hours: t.switchover_hours, predecessor_ids: t.predecessor_ids || [], capability_requirements: (t.capability_requirements || []).map(c => ({ tag_name: c.tag_name, tag_value: c.tag_value })) })
  taskOpen.value = true
}

async function handleTaskSubmit() {
  if (!selectedProject.value) return
  const payload = {
    name: tf.name, task_type: tf.task_type,
    requires_instrument: tf.task_type === 'instrument',
    est_duration_hours: tf.est_duration_hours,
    switchover_hours: tf.switchover_hours,
    predecessor_ids: tf.predecessor_ids,
    capability_requirements: tf.capability_requirements,
  }
  try {
    if (editingTask.value) {
      await updateTask(editingTask.value.id, payload as any)
      message.success('任务更新成功')
    } else {
      await addTask(selectedProject.value.id, payload as any)
      message.success('任务添加成功')
    }
    taskOpen.value = false; editingTask.value = null
    const [p, d] = await Promise.all([getProject(selectedProject.value.id), getProjectDAG(selectedProject.value.id)])
    selectedProject.value = p; dagData.value = d
  } catch { message.error('操作失败') }
}

onMounted(fetchProjects)
</script>
