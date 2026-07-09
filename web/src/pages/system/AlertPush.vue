<template>
  <div>
    <div class="page-header"><h2>智能预警推送</h2></div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 50px auto" />

    <template v-else>
      <div class="action-bar">
        <a-button @click="fetchData"><ReloadOutlined /> 刷新</a-button>
        <a-button v-if="activeTab === 'rules'" type="primary" style="margin-left: auto" @click="saveAll">保存规则</a-button>
      </div>

      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="rules" tab="预警规则">
          <a-card size="small" title="企业微信配置" :bordered="true" class="config-card">
            <a-form layout="inline" class="wecom-form">
              <a-form-item label="企业微信推送">
                <a-switch v-model:checked="pushConfig.wecom_enabled" checked-children="启用" un-checked-children="停用" />
              </a-form-item>
              <a-form-item label="CorpID">
                <a-input v-model:value="pushConfig.wecom_corp_id" placeholder="企业ID" allow-clear />
              </a-form-item>
              <a-form-item label="AgentId">
                <a-input v-model:value="pushConfig.wecom_agent_id" placeholder="应用 AgentId" allow-clear />
              </a-form-item>
              <a-form-item label="Secret">
                <a-input-password v-model:value="pushConfig.wecom_secret" placeholder="应用 Secret" />
              </a-form-item>
              <a-form-item>
                <a-button type="primary" @click="savePushConfig">保存配置</a-button>
              </a-form-item>
            </a-form>
          </a-card>

          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :lg="12" v-for="rule in rules" :key="rule.id">
              <a-card size="small" :title="rule.name" :bordered="true" class="rule-card">
                <template #extra>
                  <a-switch v-model:checked="rule.enabled" checked-children="启用" un-checked-children="停用" />
                </template>
                <a-form layout="vertical" size="small">
                  <a-form-item label="推送通道">
                    <a-space>
                      <a-switch v-model:checked="rule.enable_site" checked-children="站内" un-checked-children="站内" />
                      <a-switch v-model:checked="rule.enable_wecom" checked-children="企微" un-checked-children="企微" />
                    </a-space>
                  </a-form-item>
                  <a-form-item label="通知角色">
                    <a-select v-model:value="rule._roles" mode="multiple" :options="roleOptions" placeholder="选择角色" />
                  </a-form-item>
                  <a-form-item v-if="rule.rule_type === 'task_start_delay'" label="超时阈值(分钟)">
                    <a-input-number v-model:value="rule.threshold_minutes" :min="5" :max="480" :step="5" style="width: 100%" />
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 2px">计划开始时间后超过此分钟数未点击开始，触发预警</div>
                  </a-form-item>
                  <a-form-item v-if="rule.rule_type === 'task_end_delay'" label="预警说明">
                    <div style="font-size: 12px; color: #64748b">计划结束时间后未点击完成，自动标记为延期并通知</div>
                  </a-form-item>
                  <a-form-item v-if="rule.rule_type === 'schedule_changed'" label="预警说明">
                    <div style="font-size: 12px; color: #64748b">项目重排或插单导致排程变更时，通知受影响的任务负责人</div>
                  </a-form-item>
                  <a-form-item v-if="rule.rule_type === 'hours_exceeded'" label="超出阈值(%)">
                    <a-input-number v-model:value="rule.threshold_percent" :min="100" :max="300" :step="10" style="width: 100%" />
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 2px">实际工时超过预计工时的百分比，如 120% 表示超出 20%</div>
                  </a-form-item>
                </a-form>
              </a-card>
            </a-col>
          </a-row>
        </a-tab-pane>

        <a-tab-pane key="history" tab="推送历史">
          <a-table
            :dataSource="history"
            :columns="historyColumns"
            rowKey="id"
            size="middle"
            :pagination="{ pageSize: 12, showSizeChanger: true }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'type'">
                <a-tag :color="notificationTypeColor(record.n_type)">{{ notificationTypeLabel(record.n_type) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'channel'">
                <a-tag :color="record.channel === 'wecom' ? 'cyan' : 'blue'">{{ channelLabel(record.channel) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'delivery_status'">
                <a-tooltip v-if="record.error_message" :title="record.error_message">
                  <a-tag :color="record.delivery_status === 'success' ? 'green' : 'red'">
                    {{ deliveryStatusLabel(record.delivery_status) }}
                  </a-tag>
                </a-tooltip>
                <a-tag v-else :color="record.delivery_status === 'success' ? 'green' : 'red'">
                  {{ deliveryStatusLabel(record.delivery_status) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-space :size="4">
                  <a-tag :color="record.is_read ? 'green' : 'blue'">{{ record.is_read ? '已读' : '未读' }}</a-tag>
                  <a-tag v-if="record.is_confirmed !== null" :color="record.is_confirmed ? 'green' : 'orange'">
                    {{ record.is_confirmed ? '已确认' : '待确认' }}
                  </a-tag>
                </a-space>
              </template>
              <template v-else-if="column.key === 'created_at'">
                {{ dayjs(record.created_at).format('YYYY-MM-DD HH:mm') }}
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import {
  getAlertRules,
  getNotificationHistory,
  getPushConfig,
  updateAlertRule,
  updatePushConfig,
  type AlertRule,
  type NotificationRecord,
  type PushChannelConfig,
} from '@/services/api'

interface RuleWithRoles extends AlertRule { _roles: string[] }

const loading = ref(true)
const rules = ref<RuleWithRoles[]>([])
const history = ref<NotificationRecord[]>([])
const activeTab = ref('rules')
const pushConfig = reactive<PushChannelConfig>({
  id: 0,
  wecom_enabled: false,
  wecom_corp_id: '',
  wecom_agent_id: '',
  wecom_secret: '',
})

const roleOptions = [
  { label: '系统管理员', value: '系统管理员' },
  { label: '项目管理员', value: '项目管理员' },
  { label: '项目负责人', value: '项目负责人' },
  { label: '分析员', value: '分析员' },
]

const historyColumns = [
  { title: '推送类型', key: 'type', width: 140 },
  { title: '通道', key: 'channel', width: 90 },
  { title: '接收人', dataIndex: 'user_name', key: 'user', width: 120 },
  { title: '标题', dataIndex: 'title', key: 'title', width: 180, ellipsis: true },
  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '发送结果', key: 'delivery_status', width: 110 },
  { title: '状态', key: 'status', width: 150 },
  { title: '推送时间', key: 'created_at', width: 150 },
]

async function fetchData() {
  loading.value = true
  try {
    const [data, historyData] = await Promise.all([
      getAlertRules(),
      getNotificationHistory(),
    ])
    const config = await getPushConfig()
    rules.value = data.map(r => ({
      ...r,
      _roles: parseRoles(r.notify_roles)
    }))
    history.value = historyData
    Object.assign(pushConfig, config)
  } catch { message.error('加载预警配置失败') }
  finally { loading.value = false }
}

async function saveAll() {
  try {
    for (const r of rules.value) {
      await updateAlertRule(r.id, {
        enabled: r.enabled,
        enable_site: r.enable_site,
        enable_wecom: r.enable_wecom,
        notify_roles: JSON.stringify(r._roles),
        threshold_minutes: r.threshold_minutes,
        threshold_percent: r.threshold_percent,
      })
    }
    message.success('全部规则已保存')
  } catch { message.error('保存失败') }
}

async function savePushConfig() {
  try {
    const data = await updatePushConfig({
      wecom_enabled: pushConfig.wecom_enabled,
      wecom_corp_id: pushConfig.wecom_corp_id,
      wecom_agent_id: pushConfig.wecom_agent_id,
      wecom_secret: pushConfig.wecom_secret,
    })
    Object.assign(pushConfig, data)
    message.success('企业微信配置已保存')
  } catch {
    message.error('企业微信配置保存失败')
  }
}

function parseRoles(value: string | null) {
  if (!value) return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.filter(role => typeof role === 'string') : []
  } catch {
    return []
  }
}

function notificationTypeLabel(type: string) {
  const labels: Record<string, string> = {
    instrument_fault_reschedule: '故障重排',
    instrument_fault_schedule_conflict: '故障冲突',
    schedule_changed: '排程变更',
    task_start_delay: '开始延迟',
    task_end_delay: '结束延期',
    hours_exceeded: '工时超标',
  }
  return labels[type] || type
}

function notificationTypeColor(type: string) {
  const colors: Record<string, string> = {
    instrument_fault_schedule_conflict: 'red',
    instrument_fault_reschedule: 'orange',
    schedule_changed: 'blue',
    task_start_delay: 'gold',
    task_end_delay: 'volcano',
    hours_exceeded: 'purple',
  }
  return colors[type] || 'default'
}

function channelLabel(channel: string) {
  return channel === 'wecom' ? '企业微信' : '站内'
}

function deliveryStatusLabel(status: string) {
  return status === 'success' ? '成功' : '失败'
}

onMounted(fetchData)
</script>

<style scoped>
.rule-card {
  height: 100%;
}

.config-card {
  margin-bottom: 16px;
}

.wecom-form {
  row-gap: 12px;
}

.wecom-form :deep(.ant-form-item) {
  margin-bottom: 0;
}
</style>
