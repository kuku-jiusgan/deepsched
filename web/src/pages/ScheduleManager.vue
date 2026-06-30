<template>
  <div>
    <div class="page-header"><h2>排程管理</h2><p>生成排程、插单与动态重排</p></div>
    <div class="action-bar">
      <a-button type="primary" :loading="genLoading" @click="handleGenerate"><ThunderboltOutlined /> 生成排程</a-button>
      <a-button @click="openInsert"><PlusCircleOutlined /> 插单</a-button>
      <a-button @click="handleReschedule('local')"><ReloadOutlined /> 局部修复</a-button>
      <a-button @click="handleReschedule('project')"><ReloadOutlined /> 项目级重排</a-button>
      <a-button danger @click="handleReschedule('global')"><ReloadOutlined /> 全局重排</a-button>
      <a-button @click="handleDailyRoll"><ForwardOutlined /> 每日滚动</a-button>
    </div>
    <a-card v-if="recentSlots.length" title="最近排程结果" style="margin-top: 16px">
      <a-table :dataSource="recentSlots" rowKey="id" size="small" :columns="slotColumns" :pagination="false" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { message } from "ant-design-vue"
import { ThunderboltOutlined, PlusCircleOutlined, ReloadOutlined, ForwardOutlined } from "@ant-design/icons-vue"
import { generateSchedule, reschedule, dailyRoll, getTimeslots } from "@/services/api"
import type { TimeSlot } from "@/types"

const genLoading = ref(false)
const recentSlots = ref<TimeSlot[]>([])

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
  try { await generateSchedule(); message.success("排程生成成功"); const s = await getTimeslots(); recentSlots.value = s.slice(0, 20) }
  catch { message.error("生成失败") }
  finally { genLoading.value = false }
}
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
