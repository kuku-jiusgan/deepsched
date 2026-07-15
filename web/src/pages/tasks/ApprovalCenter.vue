<template>
  <div class="approval-page">
    <div class="page-header">
      <div>
        <h2>方案签批</h2>
        <p>集中跟踪客户方案审核，并在同意后自动衔接验证排程</p>
      </div>
      <a-button :loading="loading" @click="loadGates(false)"><ReloadOutlined /> 刷新</a-button>
    </div>

    <div class="summary-strip">
      <div><span>待签批</span><strong>{{ summary.pending }}</strong></div>
      <div><span>即将超期</span><strong class="is-warning">{{ summary.upcoming }}</strong></div>
      <div><span>已超期/结题风险</span><strong class="is-danger">{{ summary.overdue }}</strong></div>
      <div><span>已签批</span><strong class="is-success">{{ summary.approved }}</strong></div>
    </div>

    <div class="filter-bar">
      <a-input-search v-model:value="filters.keyword" placeholder="项目编号、名称、客户或方案" allowClear style="width: 280px" @search="resetAndLoad" />
      <a-select v-model:value="filters.projectId" :options="projectOptions" placeholder="全部项目" allowClear showSearch optionFilterProp="label" style="width: 220px" @change="resetAndLoad" />
      <a-select v-model:value="filters.managerId" :options="managerOptions" placeholder="全部负责人" allowClear style="width: 160px" @change="resetAndLoad" />
      <a-select v-model:value="filters.risk" :options="riskOptions" placeholder="全部风险" allowClear style="width: 160px" @change="resetAndLoad" />
      <a-range-picker v-model:value="filters.expectedRange" format="YYYY-MM-DD" @change="resetAndLoad" />
    </div>

    <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
      <a-tab-pane key="pending" :tab="`待签批 (${summary.pending})`" />
      <a-tab-pane key="approved" :tab="`已签批 (${summary.approved})`" />
    </a-tabs>

    <a-table
      :dataSource="gates"
      rowKey="id"
      size="small"
      :loading="loading"
      :pagination="pagination"
      :scroll="{ x: activeTab === 'pending' ? 1680 : 1520 }"
      @change="handleTableChange"
    >
      <a-table-column title="项目" fixed="left" width="210">
        <template #default="{ record }">
          <div class="primary-text">{{ record.project_name }}</div>
          <div class="secondary-text">{{ record.project_code }} · {{ record.client_name || '未填写客户' }}</div>
        </template>
      </a-table-column>
      <a-table-column title="方案" width="170">
        <template #default="{ record }"><span class="primary-text">{{ record.name }}</span></template>
      </a-table-column>
      <a-table-column title="项目负责人" dataIndex="project_manager_name" width="110" />
      <a-table-column title="前置任务" width="170">
        <template #default="{ record }">{{ taskNames(record.predecessor_tasks) }}</template>
      </a-table-column>
      <a-table-column title="解锁验证任务" width="190">
        <template #default="{ record }">{{ taskNames(record.unlock_tasks) }}</template>
      </a-table-column>
      <a-table-column title="提交时间" width="145">
        <template #default="{ record }">{{ formatDateTime(record.submitted_at) }}</template>
      </a-table-column>
      <a-table-column title="预计签批" width="145">
        <template #default="{ record }">{{ formatDateTime(record.expected_approval_at) }}</template>
      </a-table-column>
      <a-table-column v-if="activeTab === 'pending'" title="最迟可签批" width="145">
        <template #default="{ record }">{{ formatDateTime(record.latest_approval_at) }}</template>
      </a-table-column>
      <a-table-column v-else title="实际签批" width="145">
        <template #default="{ record }">{{ formatDateTime(record.approved_at) }}</template>
      </a-table-column>
      <a-table-column v-if="activeTab === 'approved'" title="记录人" dataIndex="approved_by_name" width="100" />
      <a-table-column title="风险/结果" width="150">
        <template #default="{ record }">
          <a-tag :color="riskMeta(record.risk_status).color">{{ riskMeta(record.risk_status).label }}</a-tag>
          <div v-if="record.schedule_status" class="secondary-text schedule-result">{{ scheduleLabel(record.schedule_status) }}</div>
        </template>
      </a-table-column>
      <a-table-column title="状态" width="110">
        <template #default="{ record }"><a-tag :color="gateMeta(record.gate_status).color">{{ gateMeta(record.gate_status).label }}</a-tag></template>
      </a-table-column>
      <a-table-column title="操作" fixed="right" width="220">
        <template #default="{ record }">
          <a-space :size="4">
            <a-button v-if="activeTab === 'pending' && record.can_operate" type="link" size="small" @click="openSubmit(record)">
              {{ record.gate_status === 'not_submitted' ? '提交签批' : '修改预计日期' }}
            </a-button>
            <a-button v-if="record.gate_status === 'waiting_approval' && record.can_operate" type="link" size="small" @click="confirmApprove(record)">记录已同意</a-button>
            <a-button v-if="record.schedule_status === 'confirmation_required' && record.can_operate" type="link" size="small" danger @click="confirmImpact(record)">确认排程影响</a-button>
            <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
            <a-button v-if="activeTab === 'pending'" type="link" size="small" @click="viewProject(record.project_id)">项目计划</a-button>
            <a-button v-else type="link" size="small" @click="viewGantt(record.project_id)">项目甘特图</a-button>
          </a-space>
        </template>
      </a-table-column>
      <template #emptyText><a-empty description="当前没有方案签批记录" /></template>
    </a-table>

    <a-modal
      v-model:open="submitOpen"
      :title="editingGate?.gate_status === 'not_submitted' ? '提交客户签批' : '修改预计签批日期'"
      okText="保存并生成预测排程"
      :confirmLoading="submitting"
      @ok="handleSubmit"
    >
      <a-form layout="vertical">
        <a-form-item label="项目方案"><a-input :value="editingGate ? `${editingGate.project_code} · ${editingGate.name}` : ''" disabled /></a-form-item>
        <a-form-item label="预计签批完成时间" required>
          <a-date-picker v-model:value="submitForm.expectedAt" showTime format="YYYY-MM-DD HH:mm" style="width: 100%" :disabledDate="disablePastDate" />
        </a-form-item>
        <a-form-item label="备注"><a-textarea v-model:value="submitForm.note" :rows="3" :maxlength="500" showCount /></a-form-item>
      </a-form>
    </a-modal>
    <a-drawer v-model:open="detailOpen" title="方案签批详情" width="520">
      <a-descriptions v-if="detailGate" :column="1" bordered size="small">
        <a-descriptions-item label="项目">{{ detailGate.project_code }} · {{ detailGate.project_name }}</a-descriptions-item>
        <a-descriptions-item label="客户">{{ detailGate.client_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="方案">{{ detailGate.name }}</a-descriptions-item>
        <a-descriptions-item label="前置任务">{{ taskNames(detailGate.predecessor_tasks) }}</a-descriptions-item>
        <a-descriptions-item label="解锁任务">{{ taskNames(detailGate.unlock_tasks) }}</a-descriptions-item>
        <a-descriptions-item label="提交时间">{{ formatDateTime(detailGate.submitted_at) }}</a-descriptions-item>
        <a-descriptions-item label="预计签批">{{ formatDateTime(detailGate.expected_approval_at) }}</a-descriptions-item>
        <a-descriptions-item label="最迟签批">{{ formatDateTime(detailGate.latest_approval_at) }}</a-descriptions-item>
        <a-descriptions-item label="实际签批">{{ formatDateTime(detailGate.approved_at) }}</a-descriptions-item>
        <a-descriptions-item label="记录人">{{ detailGate.approved_by_name || '-' }}</a-descriptions-item>
        <a-descriptions-item label="排程结果">{{ detailGate.schedule_message || scheduleLabel(detailGate.schedule_status || '-') }}</a-descriptions-item>
        <a-descriptions-item label="移动任务数">{{ detailGate.moved_tasks }}</a-descriptions-item>
        <a-descriptions-item label="项目预计完成">{{ formatDateTime(detailGate.project_expected_completion) }}</a-descriptions-item>
        <a-descriptions-item label="备注">{{ detailGate.approval_note || '-' }}</a-descriptions-item>
      </a-descriptions>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import {
  approveApprovalGate,
  confirmApprovalScheduleImpact,
  getApprovalGates,
  getProjects,
  submitApprovalGate,
} from '@/services/api'
import type { ApprovalGate, ApprovalGateStatus, ApprovalGateTaskRef, ApprovalRiskStatus } from '@/types'

const router = useRouter()
const activeTab = ref<'pending' | 'approved'>('pending')
const gates = ref<ApprovalGate[]>([])
const projects = ref<{ id: number; code: string; name: string; manager_id?: number | null; manager_name?: string }[]>([])
const loading = ref(false)
const submitOpen = ref(false)
const submitting = ref(false)
const editingGate = ref<ApprovalGate | null>(null)
const detailGate = ref<ApprovalGate | null>(null)
const detailOpen = ref(false)
const summary = reactive({ pending: 0, approved: 0, upcoming: 0, overdue: 0 })
const filters = reactive({ keyword: '', projectId: undefined as number | undefined, managerId: undefined as number | undefined, risk: undefined as string | undefined, expectedRange: null as [Dayjs, Dayjs] | null })
const submitForm = reactive({ expectedAt: null as Dayjs | null, note: '' })
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const pagination = computed<TablePaginationConfig>(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showTotal: value => `共 ${value} 条`,
}))
const projectOptions = computed(() => projects.value.map(project => ({ label: `${project.code} · ${project.name}`, value: project.id })))
const managerOptions = computed(() => Array.from(new Map(projects.value.filter(project => project.manager_id).map(project => [project.manager_id, { label: project.manager_name || `用户 ${project.manager_id}`, value: project.manager_id }])).values()))
const riskOptions = [
  { label: '正常', value: 'normal' }, { label: '即将超期', value: 'upcoming' },
  { label: '已超预计日期', value: 'overdue' }, { label: '结题风险', value: 'deadline_risk' },
]

async function loadGates(silent = true) {
  if (!silent) loading.value = true
  try {
    const result = await getApprovalGates({
      status: activeTab.value,
      keyword: filters.keyword || undefined,
      project_id: filters.projectId,
      manager_id: filters.managerId,
      risk: filters.risk,
      expected_from: filters.expectedRange?.[0].startOf('day').toISOString(),
      expected_to: filters.expectedRange?.[1].endOf('day').toISOString(),
      page: page.value,
      page_size: pageSize.value,
    })
    gates.value = result.items
    total.value = result.total
    Object.assign(summary, { pending: result.pending_count, approved: result.approved_count, upcoming: result.upcoming_count, overdue: result.overdue_count })
  } catch { message.error('加载方案签批数据失败') }
  finally { loading.value = false }
}

function resetAndLoad() { page.value = 1; loadGates(false) }
function handleTabChange() { resetAndLoad() }
function handleTableChange(value: TablePaginationConfig) { page.value = value.current || 1; pageSize.value = value.pageSize || 20; loadGates(false) }
function openSubmit(gate: ApprovalGate) {
  editingGate.value = gate
  submitForm.expectedAt = gate.expected_approval_at ? dayjs(gate.expected_approval_at) : null
  submitForm.note = gate.approval_note || ''
  submitOpen.value = true
}
async function handleSubmit() {
  if (!editingGate.value || !submitForm.expectedAt) { message.error('请选择预计签批完成时间'); return }
  submitting.value = true
  try {
    const result = await submitApprovalGate(editingGate.value.id, { expected_approval_at: submitForm.expectedAt.toISOString(), approval_note: submitForm.note || null })
    submitOpen.value = false
    message.success(result.schedule_message || '已提交客户签批并更新预测排程')
    await loadGates(true)
  } catch (error: unknown) { message.error(errorDetail(error, '提交签批失败')) }
  finally { submitting.value = false }
}
function confirmApprove(gate: ApprovalGate) {
  Modal.confirm({
    title: '确认客户已审核同意？',
    content: `确认后将以当前时间解除“${gate.name}”限制，并自动重新安排后续验证任务。`,
    okText: '确认同意并排程',
    async onOk() {
      const result = await approveApprovalGate(gate.id, { approval_note: gate.approval_note })
      message.success(result.schedule_message || '已记录客户审核同意')
      await loadGates(true)
    },
  })
}
function confirmImpact(gate: ApprovalGate) {
  if (!gate.preview_token) return
  Modal.confirm({
    title: '确认跨项目排程影响？',
    content: gate.schedule_message || '该方案需要移动低优先级项目任务，确认后将应用新的排程。',
    okText: '确认应用',
    async onOk() {
      const result = await confirmApprovalScheduleImpact(gate.id, gate.preview_token || '')
      message.success(result.schedule_message || '排程影响已确认')
      await loadGates(true)
    },
  })
}
function viewProject(projectId: number) { router.push({ path: '/projects/plan-breakdown', query: { id: projectId } }) }
function viewGantt(projectId: number) { router.push({ path: '/kanban/project-gantt', query: { project_id: projectId } }) }
function openDetail(gate: ApprovalGate) { detailGate.value = gate; detailOpen.value = true }
function taskNames(tasks: ApprovalGateTaskRef[]) { return tasks.map(task => task.name).join('、') || '-' }
function formatDateTime(value?: string | null) { return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-' }
function disablePastDate(value: Dayjs) { return value.endOf('day').isBefore(dayjs()) }
function gateMeta(status: ApprovalGateStatus) {
  return { not_submitted: { label: '待提交', color: 'default' }, waiting_approval: { label: '等待客户', color: 'blue' }, approved: { label: '已签批', color: 'green' } }[status]
}
function riskMeta(status: ApprovalRiskStatus) {
  return { normal: { label: '正常', color: 'default' }, upcoming: { label: '即将超期', color: 'gold' }, overdue: { label: '已超预计日期', color: 'orange' }, deadline_risk: { label: '结题风险', color: 'red' } }[status]
}
function scheduleLabel(status: string) {
  return { forecast: '预测排程已更新', applied: '正式排程已更新', confirmation_required: '待确认排程影响', deadline_risk: '结题日期不可满足' }[status] || status
}
function errorDetail(error: unknown, fallback: string) {
  const candidate = error as { response?: { data?: { detail?: string } } }
  return candidate.response?.data?.detail || fallback
}

onMounted(async () => {
  loading.value = true
  try { projects.value = await getProjects() } catch { projects.value = [] }
  await loadGates(true)
})
</script>

<style scoped>
.approval-page { min-width: 0; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-header h2 { margin: 0; font-size: 20px; color: var(--color-text-primary); }
.page-header p { margin: 5px 0 0; color: var(--color-text-secondary); font-size: 13px; }
.summary-strip { display: flex; flex-wrap: wrap; gap: 0; margin-bottom: 16px; border: 1px solid var(--color-border-light); border-radius: 6px; background: #fff; }
.summary-strip > div { min-width: 150px; padding: 12px 18px; border-right: 1px solid var(--color-border-light); }
.summary-strip > div:last-child { border-right: none; }
.summary-strip span { display: block; color: var(--color-text-secondary); font-size: 12px; }
.summary-strip strong { display: block; margin-top: 3px; color: var(--color-text-primary); font-size: 20px; }
.summary-strip .is-warning { color: #b45309; }
.summary-strip .is-danger { color: #dc2626; }
.summary-strip .is-success { color: #15803d; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 6px; }
.primary-text { color: var(--color-text-primary); font-weight: 600; }
.secondary-text { margin-top: 2px; color: var(--color-text-tertiary); font-size: 12px; }
.schedule-result { white-space: normal; line-height: 1.35; }
@media (max-width: 900px) {
  .summary-strip > div { flex: 1 1 50%; border-bottom: 1px solid var(--color-border-light); }
  .filter-bar > * { width: 100% !important; }
}
</style>
