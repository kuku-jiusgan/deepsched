<template>
  <div>
    <div class="page-header"><h2>排程管理</h2></div>
    <div class="action-bar">
      <a-button type="primary" :loading="genLoading" @click="handleGenerate"><ThunderboltOutlined /> 生成排程</a-button>
      <a-button @click="openInsert"><PlusCircleOutlined /> 插单</a-button>
      <a-button @click="handleReschedule('local')"><ReloadOutlined /> 局部修复</a-button>
      <a-button @click="handleReschedule('project')"><ReloadOutlined /> 项目级重排</a-button>
      <a-button danger @click="handleReschedule('global')"><ReloadOutlined /> 全局重排</a-button>
      <a-button @click="handleDailyRoll"><ForwardOutlined /> 每日滚动</a-button>
    </div>
    <a-card v-if="recentSlots.length" title="最近排程结果" style="margin-top: 16px">
      <a-table :dataSource="recentSlots" rowKey="id" size="small" :columns="slotColumns" :pagination="false">
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
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { message, Modal } from "ant-design-vue"
import { ThunderboltOutlined, PlusCircleOutlined, ReloadOutlined, ForwardOutlined } from "@ant-design/icons-vue"
import { generateSchedule, reschedule, dailyRoll, getTimeslots } from "@/services/api"
import dayjs from "dayjs"
import type { TimeSlot } from "@/types"

const genLoading = ref(false)
const STORAGE_KEY = "schedule_recent_slots"
const recentSlots = ref<TimeSlot[]>(loadFromStorage())

function loadFromStorage(): TimeSlot[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveToStorage(slots: TimeSlot[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(slots)) } catch { /* quota exceeded */ }
}

const tierLabels: Record<string, string> = { frozen: '冻结', confirmed: '确认', forecast: '预测' }
const statusLabels: Record<string, string> = { completed: '已完成', running: '运行中', scheduled: '已排程', interrupted: '已中断', pending: '待处理' }

const slotColumns = [
  { title: "仪器", dataIndex: "instrument_name", key: "inst" },
  { title: "项目", dataIndex: "project_name", key: "proj" },
  { title: "任务", dataIndex: "task_name", key: "task" },
  { title: "开始", dataIndex: "plan_start", key: "start" },
  { title: "结束", dataIndex: "plan_end", key: "end" },
  { title: "层级", dataIndex: "tier", key: "tier" },
  { title: "状态", dataIndex: "status", key: "status" },
]

async function handleGenerate() {
  genLoading.value = true
  try {
    const result = await generateSchedule()
    if (result.status !== "ok") {
      Modal.error({ title: "排程失败", content: result.message || "请检查任务、仪器和项目时间配置。" })
      return
    }
    message.success("排程生成成功")
    // Small delay to ensure DB commit is visible
    await new Promise(r => setTimeout(r, 300))
    const s = await getTimeslots()
    recentSlots.value = s.slice(0, 20)
    saveToStorage(recentSlots.value)
  } catch (e: any) {
    console.error('Generate failed:', e)
    message.error(e?.response?.data?.detail || '生成失败')
  }
  finally { genLoading.value = false }
}
onMounted(async () => {
  if (recentSlots.value.length === 0) {
    try { const s = await getTimeslots(); recentSlots.value = s.slice(0, 20); saveToStorage(recentSlots.value) } catch { /* ignore */ }
  }
})

function openInsert() { message.info("插单功能开发中") }
async function handleReschedule(s: string) {
  try { await reschedule({ trigger_type: "manual", strategy: s }); message.success("重排完成") }
  catch { message.error("重排失败") }
}
async function handleDailyRoll() {
  try { await dailyRoll(); message.success("每日滚动完成") }
  catch { message.error("滚动失败") }
}
</script>
