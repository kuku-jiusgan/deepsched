<template>
  <div>
    <div class="page-header">
      <h2>排程规则配置</h2>
    </div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 80px auto" />

    <template v-else>
      <!-- 决策变量 -->
      <a-card title="决策变量" size="small" style="margin-bottom: 16px">
        <template #extra><a-tag color="blue">{{ decisionVars.length }} 项</a-tag></template>
        <div v-for="rule in decisionVars" :key="rule.id" class="rule-row">
          <div class="rule-info">
            <div class="rule-name">{{ rule.name }}</div>
            <div class="rule-desc">{{ rule.description }}</div>
          </div>
          <div class="rule-params">
            <template v-if="rule.code === 'time_granularity'">
              <span style="margin-right: 8px; color: #64748b; font-size: 13px">当前值：</span>
              <a-input-number
                v-model:value="rule.params.value"
                :min="15"
                :max="120"
                :step="15"
                style="width: 100px"
                @change="(v: number | null) => saveRuleParam(rule, 'value', v ?? 30)"
              />
              <span style="margin: 0 8px; color: #64748b; font-size: 13px">分钟</span>
            </template>
            <template v-else-if="rule.code === 'planning_horizon'">
              <span style="margin-right: 8px; color: #64748b; font-size: 13px">当前值：</span>
              <a-input-number
                v-model:value="rule.params.value"
                :min="7"
                :max="180"
                :step="1"
                style="width: 100px"
                @change="(v: number | null) => saveRuleParam(rule, 'value', v ?? 90)"
              />
              <span style="margin: 0 8px; color: #64748b; font-size: 13px">天</span>
            </template>
          </div>
        </div>
      </a-card>

      <!-- 约束条件 -->
      <a-card title="约束条件" size="small" style="margin-bottom: 16px">
        <template #extra>
          <a-space>
            <a-tag :color="constraintEnabledCount === constraints.length ? 'green' : 'orange'">
              {{ constraintEnabledCount }}/{{ constraints.length }} 已启用
            </a-tag>
          </a-space>
        </template>
        <div v-for="rule in constraints" :key="rule.id" class="rule-row" :class="{ 'rule-disabled': !rule.is_enabled }">
          <div class="rule-info">
            <div class="rule-name">
              <span :style="{ color: rule.is_enabled ? '#1e293b' : '#94a3b8' }">{{ rule.name }}</span>
              <a-tag v-if="rule.params?.strict" color="red" style="margin-left: 6px; font-size: 10px">硬约束</a-tag>
              <a-tag v-else color="blue" style="margin-left: 6px; font-size: 10px">软约束</a-tag>
            </div>
            <div class="rule-desc" :style="{ color: rule.is_enabled ? '#64748b' : '#cbd5e1' }">{{ rule.description }}</div>
          </div>
          <div class="rule-params">
            <template v-if="rule.code === 'automated_night_window'">
              <span style="font-size: 12px; color: #94a3b8">夜间</span>
              <a-input-number v-model:value="rule.params.night_start" :min="18" :max="23" size="small" style="width: 60px" :disabled="!rule.is_enabled" @change="(v: number | null) => saveRuleParam(rule, 'night_start', v ?? 22)" />
              <span style="font-size: 12px; color: #94a3b8">:00 - 次日</span>
              <a-input-number v-model:value="rule.params.night_end" :min="4" :max="10" size="small" style="width: 60px" :disabled="!rule.is_enabled" @change="(v: number | null) => saveRuleParam(rule, 'night_end', v ?? 8)" />
              <span style="font-size: 12px; color: #94a3b8">:00</span>
            </template>
            <template v-else-if="rule.code === 'manual_hours'">
              <span style="font-size: 12px; color: #94a3b8">白天</span>
              <a-input-number v-model:value="rule.params.day_start" :min="6" :max="10" size="small" style="width: 60px" :disabled="!rule.is_enabled" @change="(v: number | null) => saveRuleParam(rule, 'day_start', v ?? 8)" />
              <span style="font-size: 12px; color: #94a3b8">:00 - </span>
              <a-input-number v-model:value="rule.params.day_end" :min="18" :max="24" size="small" style="width: 60px" :disabled="!rule.is_enabled" @change="(v: number | null) => saveRuleParam(rule, 'day_end', v ?? 22)" />
              <span style="font-size: 12px; color: #94a3b8">:00</span>
            </template>
            <template v-else-if="rule.code === 'switchover_cost'">
              <span style="font-size: 12px; color: #94a3b8">基准切换耗时</span>
              <a-input-number v-model:value="rule.params.base_hours" :min="0" :max="8" :step="0.5" size="small" style="width: 70px" :disabled="!rule.is_enabled" @change="(v: number | null) => saveRuleParam(rule, 'base_hours', v ?? 0.5)" />
              <span style="font-size: 12px; color: #94a3b8">小时</span>
            </template>
            <template v-else-if="rule.code === 'freezing'">
              <span style="font-size: 12px; color: #94a3b8">冻结窗口</span>
              <a-input-number v-model:value="rule.params.freeze_horizon_hours" :min="0" :max="168" size="small" style="width: 70px" :disabled="!rule.is_enabled" @change="(v: number | null) => saveRuleParam(rule, 'freeze_horizon_hours', v ?? 72)" />
              <span style="font-size: 12px; color: #94a3b8">小时</span>
            </template>
          </div>
          <div class="rule-toggle">
            <a-switch v-model:checked="rule.is_enabled" size="small" @change="toggleRule(rule)" />
          </div>
        </div>
      </a-card>

      <!-- 目标函数 -->
      <a-card title="目标函数" size="small" style="margin-bottom: 16px">
        <template #extra><a-tag color="purple">{{ objectives.length }} 项目标</a-tag></template>
        <div v-for="rule in objectives" :key="rule.id" class="rule-row" :class="{ 'rule-disabled': !rule.is_enabled }">
          <div class="rule-info">
            <div class="rule-name">
              <span :style="{ color: rule.is_enabled ? '#1e293b' : '#94a3b8' }">{{ rule.name }}</span>
              <a-tag v-if="rule.code === 'weighted_tardiness'" color="red" style="margin-left: 6px; font-size: 10px">主目标</a-tag>
              <a-tag v-else color="default" style="margin-left: 6px; font-size: 10px">次目标</a-tag>
            </div>
            <div class="rule-desc" :style="{ color: rule.is_enabled ? '#64748b' : '#cbd5e1' }">{{ rule.description }}</div>
          </div>
          <div class="rule-params">
            <span style="font-size: 12px; color: #94a3b8; margin-right: 6px">权重</span>
            <a-input-number
              v-model:value="rule.params.weight"
              :min="0"
              :max="10"
              :step="0.1"
              size="small"
              style="width: 80px"
              :disabled="!rule.is_enabled"
              @change="(v: number | null) => saveRuleParam(rule, 'weight', v ?? 0)"
            />
          </div>
          <div class="rule-toggle">
            <a-switch v-model:checked="rule.is_enabled" size="small" @change="toggleRule(rule)" />
          </div>
        </div>
      </a-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getScheduleRules, updateScheduleRule, toggleScheduleRule, type ScheduleRule } from '@/services/api'

const rules = ref<ScheduleRule[]>([])
const loading = ref(true)

const decisionVars = computed(() => rules.value.filter(r => r.category === 'decision_variable'))
const constraints = computed(() => rules.value.filter(r => r.category === 'constraint'))
const objectives = computed(() => rules.value.filter(r => r.category === 'objective'))
const constraintEnabledCount = computed(() => constraints.value.filter(r => r.is_enabled).length)

async function fetchRules() {
  loading.value = true
  try {
    rules.value = await getScheduleRules()
  } catch {
    message.error('加载排程规则失败')
  } finally {
    loading.value = false
  }
}

async function saveRuleParam(rule: ScheduleRule, key: string, value: any) {
  const newParams = { ...rule.params, [key]: value }
  try {
    await updateScheduleRule(rule.id, { params: newParams })
    rule.params = newParams
    message.success(`${rule.name} 已更新`)
  } catch {
    message.error('保存失败')
  }
}

async function toggleRule(rule: ScheduleRule) {
  try {
    const updated = await toggleScheduleRule(rule.id)
    rule.is_enabled = updated.is_enabled
  } catch {
    rule.is_enabled = !rule.is_enabled
    message.error('切换失败')
  }
}

onMounted(fetchRules)
</script>

<style scoped>
.rule-row {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f1f5f9;
  gap: 16px;
}
.rule-row:last-child { border-bottom: none; }
.rule-disabled { opacity: 0.55; }
.rule-info { flex: 1; min-width: 0; }
.rule-name { font-size: 14px; font-weight: 500; margin-bottom: 2px; }
.rule-desc { font-size: 12px; color: #64748b; line-height: 1.4; }
.rule-params { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.rule-toggle { flex-shrink: 0; }
</style>
