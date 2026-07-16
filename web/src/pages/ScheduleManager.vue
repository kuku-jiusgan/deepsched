<template>
  <div class="schedule-engine">
    <div class="page-header">
      <h2>自动排程引擎</h2>
      <p>查看全部排程，并在确有需要时重新优化所有可移动任务。</p>
    </div>

    <section class="reschedule-panel" aria-labelledby="global-reschedule-title">
      <div>
        <h3 id="global-reschedule-title">全局重排</h3>
        <p>保留冻结、运行中和已完成的日程，撤销其余可移动排程后重新求解。</p>
      </div>
      <a-button type="primary" danger :loading="rescheduleLoading" @click="confirmGlobalReschedule">
        <ReloadOutlined /> 全局重排
      </a-button>
    </section>

    <section class="schedule-section" aria-labelledby="all-schedules-title">
      <div class="section-header">
        <div>
          <h3 id="all-schedules-title">全部排程</h3>
          <p>{{ scheduleSummary }}</p>
        </div>
        <a-button :loading="tableLoading" @click="loadSchedules">
          <ReloadOutlined /> 刷新
        </a-button>
      </div>

      <a-table
        :dataSource="allSlots"
        rowKey="id"
        size="small"
        :columns="slotColumns"
        :loading="tableLoading"
        :pagination="paginationConfig"
        :scroll="{ x: 1180 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'tier'">
            <a-tag :color="record.tier === 'frozen' ? 'blue' : record.tier === 'confirmed' ? 'green' : 'default'">{{ tierLabels[record.tier] || record.tier }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'completed' ? 'green' : record.status === 'running' ? 'blue' : 'default'">{{ statusLabels[record.status] || record.status }}</a-tag>
          </template>
          <template v-else-if="column.key === 'start'">{{ dayjs(record.plan_start).format('YYYY-MM-DD HH:mm') }}</template>
          <template v-else-if="column.key === 'end'">{{ dayjs(record.plan_end).format('YYYY-MM-DD HH:mm') }}</template>
        </template>
      </a-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { isAxiosError } from "axios"
import { message, Modal } from "ant-design-vue"
import { ReloadOutlined } from "@ant-design/icons-vue"
import { getTimeslots, reschedule } from "@/services/api"
import dayjs from "dayjs"
import type { TimeSlot } from "@/types"

const allSlots = ref<TimeSlot[]>([])
const tableLoading = ref(false)
const rescheduleLoading = ref(false)

const tierLabels: Record<string, string> = { frozen: '冻结', confirmed: '确认', forecast: '预测' }
const statusLabels: Record<string, string> = {
  completed: '已完成', running: '运行中', scheduled: '已排程',
  interrupted: '已中断', blocked: '已阻塞', pending: '待处理',
}

const slotColumns = [
  { title: "仪器编号", dataIndex: "instrument_code", key: "instCode", width: 150 },
  { title: "仪器", dataIndex: "instrument_name", key: "inst", width: 180 },
  { title: "项目编号", dataIndex: "project_code", key: "projectCode", width: 140 },
  { title: "项目", dataIndex: "project_name", key: "proj", width: 220 },
  { title: "任务", dataIndex: "task_name", key: "task" },
  { title: "负责人", dataIndex: "assignee_name", key: "assignee", width: 110 },
  { title: "开始", dataIndex: "plan_start", key: "start", width: 150 },
  { title: "结束", dataIndex: "plan_end", key: "end", width: 150 },
  { title: "层级", dataIndex: "tier", key: "tier", width: 80 },
  { title: "状态", dataIndex: "status", key: "status", width: 90 },
]

const paginationConfig = {
  defaultPageSize: 20,
  showSizeChanger: true,
  pageSizeOptions: ['20', '50', '100'],
  showTotal: (total: number) => `共 ${total} 条排程`,
}

const scheduleSummary = computed(() => {
  const counts = allSlots.value.reduce<Record<string, number>>((result, slot) => {
    result[slot.tier] = (result[slot.tier] || 0) + 1
    return result
  }, {})
  return `共 ${allSlots.value.length} 条 · 冻结 ${counts.frozen || 0} · 确认 ${counts.confirmed || 0} · 预测 ${counts.forecast || 0}`
})

onMounted(loadSchedules)

async function loadSchedules() {
  tableLoading.value = true
  try {
    allSlots.value = await getTimeslots()
  } catch (error: unknown) {
    message.error(errorDetail(error, '排程信息加载失败'))
  } finally {
    tableLoading.value = false
  }
}

function confirmGlobalReschedule() {
  Modal.confirm({
    title: '确认执行全局重排？',
    content: '确认期和预测期内的可移动日程将被撤销并重新生成；冻结、运行中和已完成的日程保持不变。',
    okText: '确认重排',
    okType: 'danger',
    cancelText: '取消',
    onOk: executeGlobalReschedule,
  })
}

async function executeGlobalReschedule() {
  rescheduleLoading.value = true
  try {
    const result = await reschedule({ trigger_type: 'manual', strategy: 'global' })
    if (result.status !== 'ok') {
      Modal.error({ title: '全局重排失败', content: result.message || '当前任务无法完成全局重排。' })
      return
    }
    message.success(result.message || '全局重排完成')
    await loadSchedules()
  } catch (error: unknown) {
    Modal.error({ title: '全局重排失败', content: errorDetail(error, '服务器内部错误，请稍后重试。') })
  } finally {
    rescheduleLoading.value = false
  }
}

function errorDetail(error: unknown, fallback: string) {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail || fallback
  }
  return fallback
}
</script>

<style scoped>
.schedule-engine { max-width: 1600px; }
.reschedule-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px;
  margin-bottom: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.reschedule-panel h3, .section-header h3 { margin: 0; font-size: 15px; }
.reschedule-panel p, .section-header p {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.schedule-section {
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border-light);
}
.schedule-section :deep(.ant-table-wrapper) { padding: 0 16px 16px; }
@media (max-width: 720px) {
  .reschedule-panel, .section-header { align-items: flex-start; flex-direction: column; }
  .reschedule-panel .ant-btn, .section-header .ant-btn { width: 100%; }
}
</style>
