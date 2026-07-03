<template>
  <div>
    <div class="page-header"><h2>智能预警推送</h2></div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 50px auto" />

    <template v-else>
      <div class="action-bar">
        <span style="font-size: 12px; color: #94a3b8">配置预警规则，系统将根据规则自动推送通知给对应角色的人员</span>
        <a-button type="primary" size="small" style="margin-left: auto" @click="saveAll">保存全部</a-button>
      </div>

      <a-row :gutter="[16, 16]">
        <a-col :span="12" v-for="rule in rules" :key="rule.id">
          <a-card size="small" :title="rule.name" :bordered="true">
            <template #extra>
              <a-switch v-model:checked="rule.enabled" checked-children="启用" un-checked-children="停用" />
            </template>
            <a-form layout="vertical" size="small">
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getAlertRules, updateAlertRule, type AlertRule } from '@/services/api'

interface RuleWithRoles extends AlertRule { _roles: string[] }

const loading = ref(true)
const rules = ref<RuleWithRoles[]>([])

const roleOptions = [
  { label: '系统管理员', value: '系统管理员' },
  { label: '项目管理员', value: '项目管理员' },
  { label: '项目负责人', value: '项目负责人' },
  { label: '分析员', value: '分析员' },
]

async function fetchRules() {
  loading.value = true
  try {
    const data = await getAlertRules()
    rules.value = data.map(r => ({
      ...r,
      _roles: r.notify_roles ? JSON.parse(r.notify_roles) : []
    }))
  } catch { message.error('加载规则失败') }
  finally { loading.value = false }
}

async function saveAll() {
  try {
    for (const r of rules.value) {
      await updateAlertRule(r.id, {
        enabled: r.enabled,
        notify_roles: JSON.stringify(r._roles),
        threshold_minutes: r.threshold_minutes,
        threshold_percent: r.threshold_percent,
      })
    }
    message.success('全部规则已保存')
  } catch { message.error('保存失败') }
}

onMounted(() => { fetchRules() })
</script>
