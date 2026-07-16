<template>
  <div class="today-card-group approval-group">
    <div class="today-card-group-title">
      <span class="today-card-dot" />
      <span>方案签批确认</span>
    </div>
    <div v-if="actionableGates.length" class="today-card-stack">
      <article v-for="gate in actionableGates" :key="gate.id" class="today-card">
        <div class="today-card-meta">
          <a-tag :color="gateMeta(gate.gate_status).color">{{ gateMeta(gate.gate_status).label }}</a-tag>
          <a-tag v-if="gate.risk_status !== 'normal'" :color="riskMeta(gate.risk_status).color">{{ riskMeta(gate.risk_status).label }}</a-tag>
        </div>
        <div class="today-card-lines">
          <div><span>项目：</span>{{ gate.project_code }} · {{ gate.project_name }}</div>
          <div><span>方案：</span>{{ gate.name }}</div>
          <div><span>负责人：</span>{{ gate.assignee_name || '未指定' }}</div>
          <div><span>提交时间：</span>{{ formatDateTime(gate.submitted_at) }}</div>
          <div><span>预计签批：</span>{{ formatDateTime(gate.expected_approval_at) }}</div>
          <div><span>最迟签批：</span>{{ formatDateTime(gate.latest_approval_at) }}</div>
          <div><span>解锁任务：</span>{{ taskNames(gate.unlock_tasks) }}</div>
        </div>
        <div class="today-card-choice">请选择：</div>
        <div class="today-card-actions">
          <a-button v-if="gate.gate_status !== 'approved'" size="small" class="workspace-action-button workspace-action-button-secondary" @click="openExpectedApproval(gate)">预计签批时间</a-button>
          <a-button v-if="gate.gate_status !== 'approved'" size="small" class="workspace-action-button workspace-action-button-success" @click="confirmApprove(gate)">确认签批</a-button>
          <a-button v-if="gate.schedule_status === 'confirmation_required'" size="small" class="workspace-action-button workspace-action-button-warning" @click="confirmImpact(gate)">确认排程影响</a-button>
          <a-button size="small" class="workspace-action-button workspace-action-button-secondary" @click="viewHistory">查看详情</a-button>
        </div>
      </article>
    </div>
    <div v-else class="today-card-empty">暂无方案签批确认事项</div>

    <a-modal
      v-model:open="expectedModalOpen"
      title="填写预计签批时间"
      ok-text="保存并生成预测排程"
      cancel-text="取消"
      :confirm-loading="expectedSubmitting"
      :ok-button-props="{ disabled: !expectedApprovalAt }"
      :cancel-button-props="{ disabled: expectedSubmitting }"
      :mask-closable="!expectedSubmitting"
      :closable="!expectedSubmitting"
      :keyboard="!expectedSubmitting"
      @ok="saveExpectedApproval"
    >
      <a-form layout="vertical">
        <a-form-item label="预计签批完成时间" required>
          <a-date-picker
            v-model:value="expectedApprovalAt"
            :show-time="{ format: 'HH:mm', minuteStep: 30 }"
            format="YYYY-MM-DD HH:mm"
            :disabled-date="disabledExpectedDate"
            style="width: 100%"
            @change="normalizeExpectedApprovalAt"
          />
        </a-form-item>
      </a-form>
      <p class="expected-approval-help">保存后将从该时间起预测安排后续任务；如果需要调整其他项目排程，系统会另行提示确认。</p>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { approveApprovalGate, confirmApprovalScheduleImpact, submitApprovalGate } from '@/services/api'
import type { ApprovalGate, ApprovalGateStatus, ApprovalGateTaskRef, ApprovalRiskStatus } from '@/types'

interface Props { approvalGates: ApprovalGate[] }

const props = defineProps<Props>()
const emit = defineEmits<{ refreshed: [] }>()
const router = useRouter()
const actionableGates = computed(() => props.approvalGates.filter(gate => gate.can_operate && (gate.gate_status !== 'approved' || gate.schedule_status === 'confirmation_required')))
const expectedModalOpen = ref(false)
const expectedSubmitting = ref(false)
const expectedGate = ref<ApprovalGate | null>(null)
const expectedApprovalAt = ref<Dayjs | null>(null)

function openExpectedApproval(gate: ApprovalGate) {
  expectedGate.value = gate
  const latestApprovalAt = gate.latest_approval_at ? dayjs(gate.latest_approval_at) : null
  const defaultExpectedAt = gate.expected_approval_at
    ? dayjs(gate.expected_approval_at)
    : latestApprovalAt?.isAfter(dayjs())
      ? latestApprovalAt
      : dayjs().add(1, 'day').minute(0).second(0)
  expectedApprovalAt.value = floorToHalfHour(defaultExpectedAt)
  expectedModalOpen.value = true
}

function floorToHalfHour(value: Dayjs) {
  const minute = value.minute() < 30 ? 0 : 30
  return value.minute(minute).second(0).millisecond(0)
}

function normalizeExpectedApprovalAt(value: Dayjs | null) {
  expectedApprovalAt.value = value ? floorToHalfHour(value) : null
}

function disabledExpectedDate(value: Dayjs) {
  return value.endOf('day').isBefore(dayjs())
}

async function saveExpectedApproval() {
  const gate = expectedGate.value
  const expectedAt = expectedApprovalAt.value ? floorToHalfHour(expectedApprovalAt.value) : null
  if (!gate || !expectedAt) return
  if (!expectedAt.isAfter(dayjs())) {
    message.warning('预计签批时间必须晚于当前时间')
    return
  }
  expectedSubmitting.value = true
  try {
    const result = await submitApprovalGate(gate.id, {
      expected_approval_at: expectedAt.format('YYYY-MM-DDTHH:mm:ss'),
      approval_note: gate.approval_note,
    })
    expectedModalOpen.value = false
    if (result.schedule_status === 'forecast') {
      message.success('预计签批时间已保存，预测排程已更新')
    } else {
      message.warning(result.schedule_message || '预计签批时间已保存，请确认预测排程影响')
    }
    emit('refreshed')
  } catch (error: unknown) {
    message.error(errorDetail(error, '保存预计签批时间失败'))
  } finally {
    expectedSubmitting.value = false
  }
}

function confirmApprove(gate: ApprovalGate) {
  Modal.confirm({
    title: '确认方案签批已完成？',
    content: `确认后将以当前时间完成“${gate.name}”，并自动重新安排后续验证任务。`,
    okText: '确认完成并排程',
    async onOk() {
      try {
        const result = await approveApprovalGate(gate.id, { approval_note: gate.approval_note })
        if (result.schedule_status === 'confirmation_required') message.warning(result.schedule_message || '签批已记录，请继续确认跨项目排程影响')
        else message.success(result.schedule_message || '已记录客户审核同意')
        emit('refreshed')
      } catch (error: unknown) { message.error(errorDetail(error, '记录签批同意失败')); throw error }
    },
  })
}

function confirmImpact(gate: ApprovalGate) {
  if (!gate.preview_token) return
  Modal.confirm({
    title: '确认跨项目排程影响？',
    content: gate.schedule_message || '该方案需要移动同优先级或低优先级的未开始项目任务，确认后将应用新的排程。',
    okText: '确认应用',
    async onOk() {
      try {
        const result = await confirmApprovalScheduleImpact(gate.id, gate.preview_token || '')
        message.success(result.schedule_message || '排程影响已确认')
        emit('refreshed')
      } catch (error: unknown) { message.error(errorDetail(error, '确认排程影响失败')); throw error }
    },
  })
}

function viewHistory() { router.push('/tasks/approvals') }
function taskNames(tasks: ApprovalGateTaskRef[]) { return tasks.map(task => task.name).join('、') || '-' }
function formatDateTime(value?: string | null) { return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-' }
function gateMeta(status: ApprovalGateStatus) {
  return { not_submitted: { label: '待提交', color: 'default' }, waiting_approval: { label: '等待客户', color: 'blue' }, approved: { label: '已签批', color: 'green' } }[status]
}
function riskMeta(status: ApprovalRiskStatus) {
  return { normal: { label: '正常', color: 'default' }, upcoming: { label: '即将超期', color: 'gold' }, overdue: { label: '已超预计日期', color: 'orange' }, deadline_risk: { label: '结题风险', color: 'red' } }[status]
}
function errorDetail(error: unknown, fallback: string) {
  const candidate = error as { response?: { data?: { detail?: string } } }
  return candidate.response?.data?.detail || fallback
}
</script>

<style scoped>
.approval-group { order: 2; min-width: 0; padding: var(--space-sm); background: var(--color-bg); border: 1px solid var(--color-border-light); border-radius: var(--radius-md); }
.today-card-group-title { display: flex; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-sm); color: var(--color-text-primary); font-weight: 600; }
.today-card-dot { width: 8px; height: 8px; border-radius: 999px; background: var(--color-accent); }
.today-card-stack { display: flex; flex-direction: column; gap: var(--space-sm); }
.today-card { padding: var(--space-md); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.today-card-meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-sm); }
.today-card-lines { display: flex; flex-direction: column; gap: 3px; color: var(--color-text-primary); font-size: 0.84rem; line-height: 1.55; }
.today-card-lines span { color: var(--color-text-secondary); }
.today-card-choice { margin: var(--space-sm) 0 var(--space-xs); color: var(--color-text-secondary); font-size: 0.78rem; }
.today-card-actions { display: flex; flex-wrap: wrap; gap: var(--space-xs); }
.today-card-empty { min-height: 120px; display: flex; align-items: center; justify-content: center; color: var(--color-text-tertiary); background: var(--color-surface); border: 1px dashed var(--color-border); border-radius: var(--radius-sm); font-size: 0.82rem; }
.expected-approval-help { margin: 0; color: var(--color-text-secondary); font-size: 0.84rem; line-height: 1.55; }
</style>
