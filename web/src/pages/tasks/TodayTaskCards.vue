<template>
  <section class="today-work">
    <div class="today-work-header">
      <h3>今日任务卡片</h3>
    </div>

    <div class="today-card-grid">
      <div v-for="group in todayCardGroups" :key="group.key" class="today-card-group">
        <div class="today-card-group-title">
          <span class="today-card-dot" :class="'today-card-dot-' + group.key" />
          <span>{{ group.title }}</span>
          <a-tag>{{ group.cards.length }}</a-tag>
        </div>

        <div v-if="group.cards.length" class="today-card-stack">
          <article v-for="card in group.cards" :key="card.key" class="today-card">
            <div class="today-card-meta">
              <a-tag :color="card.tagColor">{{ card.tagText }}</a-tag>
              <span>{{ card.statusText }}</span>
            </div>

            <div class="today-card-lines">
              <div><span>项目：</span>{{ card.projectText }}</div>
              <div><span>任务：</span>{{ card.taskText }}</div>
              <div><span>仪器：</span>{{ card.instrumentText }}</div>
              <div><span>负责人：</span>{{ card.ownerText }}</div>
              <div><span>当前排程：</span>{{ card.scheduleText }}</div>
              <div v-if="card.delayText"><span>延期：</span>{{ card.delayText }}</div>
            </div>

            <div class="today-card-choice">请选择：</div>
            <div v-if="card.nightRunSummary" class="today-card-night-summary">
              {{ card.nightRunSummary }}
            </div>
            <div class="today-card-actions">
              <a-popconfirm
                title="确认该任务已经完成？"
                ok-text="确认完成"
                cancel-text="再检查一下"
                @confirm="emit('complete', card.task)"
              >
                <a-button size="small" class="task-action-button-complete">确认完成</a-button>
              </a-popconfirm>
              <a-button size="small" type="primary" @click="openAutoSequence(card)">夜间运行</a-button>
              <a-button size="small" @click="handleCardAction(card, '释放仪器')">释放仪器</a-button>
              <a-button size="small" danger @click="openDelayReport(card)">延期使用</a-button>
            </div>
          </article>
        </div>

        <div v-else class="today-card-empty">
          暂无{{ group.title }}事项
        </div>
      </div>
    </div>

    <a-modal
      v-model:open="autoSequenceOpen"
      title="夜间运行"
      ok-text="提交"
      cancel-text="取消"
      :confirm-loading="autoSequenceSubmitting"
      @ok="submitAutoSequence"
    >
      <div v-if="selectedCard" class="modal-task-summary">
        {{ selectedCard.projectText }} · {{ selectedCard.taskText }} · {{ selectedCard.instrumentText }}
      </div>
      <a-form layout="vertical">
        <a-form-item label="自动序列预计时长">
          <a-input-number v-model:value="autoSequenceForm.durationHours" :min="0.5" :step="0.5" addon-after="小时" style="width: 100%" />
        </a-form-item>
        <a-form-item label="最早开始时间">
          <a-input v-model:value="autoSequenceForm.earliestStart" />
        </a-form-item>
        <a-form-item label="最晚结束时间">
          <a-input v-model:value="autoSequenceForm.latestEnd" />
        </a-form-item>
        <a-form-item label="是否需要人在场启动">
          <a-radio-group v-model:value="autoSequenceForm.requiresOperator">
            <a-radio :value="true">是</a-radio>
            <a-radio :value="false">否</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="autoSequenceForm.remark" :rows="3" placeholder="补充序列、样品或交接注意事项" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="delayReportOpen"
      title="异常/延期确认"
      ok-text="提交并顺延排程"
      cancel-text="取消"
      :confirm-loading="delaySubmitting"
      @ok="submitDelayReport"
    >
      <div v-if="selectedCard" class="modal-task-summary">
        {{ selectedCard.projectText }} · {{ selectedCard.taskText }} · {{ selectedCard.instrumentText }}
      </div>
      <a-form layout="vertical">
        <a-form-item label="需要延期多久">
          <a-input-number v-model:value="delayForm.delayHours" :min="0.5" :step="0.5" addon-after="小时" style="width: 100%" />
        </a-form-item>
        <a-form-item label="异常原因" required>
          <a-textarea v-model:value="delayForm.reason" :rows="4" placeholder="例如：样品前处理超时、仪器状态异常、方法参数需要重新确认" />
        </a-form-item>
      </a-form>
      <div class="delay-hint">
        提交后会延长当前任务排程，并将同项目或同仪器的后续排程整体后移。
      </div>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { recordNightRun, reportTaskDelay, type MyTask } from '@/services/api'
import dayjs from 'dayjs'

type TodayCardCategory = 'completion' | 'exception'
type TodayCardGroupKey = TodayCardCategory

interface Props {
  tasks: MyTask[]
}

interface StoredUser {
  display_name?: string
  username?: string
}

interface TodayTaskCard {
  key: string
  category: TodayCardCategory
  task: MyTask
  projectText: string
  taskText: string
  instrumentText: string
  ownerText: string
  scheduleText: string
  tagText: string
  tagColor: string
  statusText: string
  earliestStart: string
  latestEnd: string
  nightRunSummary: string
  delayText: string
}

interface TodayCardGroup {
  key: TodayCardGroupKey
  title: string
  cards: TodayTaskCard[]
}

interface AutoSequenceForm {
  durationHours: number
  earliestStart: string
  latestEnd: string
  requiresOperator: boolean
  remark: string
}

interface StoredAutoSequenceForm extends AutoSequenceForm {
  savedAt: string
}

interface DelayForm {
  delayHours: number
  reason: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  complete: [task: MyTask]
  refreshed: []
}>()

const NIGHT_RESERVE_END = '次日 08:30'
const DEFAULT_NIGHT_START = '17:30'
const DEFAULT_SEQUENCE_DURATION_HOURS = 8
const DEFAULT_DELAY_HOURS = 1
const NIGHT_RUN_STORAGE_PREFIX = 'deepsched:today-night-run'

const autoSequenceOpen = ref(false)
const delayReportOpen = ref(false)
const autoSequenceSubmitting = ref(false)
const delaySubmitting = ref(false)
const selectedCard = ref<TodayTaskCard | null>(null)
const autoSequenceForm = reactive<AutoSequenceForm>({
  durationHours: DEFAULT_SEQUENCE_DURATION_HOURS,
  earliestStart: DEFAULT_NIGHT_START,
  latestEnd: NIGHT_RESERVE_END,
  requiresOperator: false,
  remark: '',
})
const delayForm = reactive<DelayForm>({
  delayHours: DEFAULT_DELAY_HOURS,
  reason: '',
})
const nightRunRevision = ref(0)

const todayTasks = computed(() => props.tasks.filter(isTodayTask))

const todayCardGroups = computed<TodayCardGroup[]>(() => {
  const completionCards = todayTasks.value
    .filter(task => !isExceptionConfirmTask(task))
    .map(task => buildTodayCard(task, 'completion'))
  const exceptionCards = todayTasks.value
    .filter(isExceptionConfirmTask)
    .map(task => buildTodayCard(task, 'exception'))

  return [
    { key: 'completion', title: '任务完成确认', cards: completionCards },
    { key: 'exception', title: '异常/延期确认', cards: exceptionCards },
  ]
})

function currentUserName() {
  const rawUser = localStorage.getItem('user')
  if (!rawUser) return '当前用户'
  try {
    const user = JSON.parse(rawUser) as StoredUser
    return user.display_name || user.username || '当前用户'
  } catch {
    return '当前用户'
  }
}

function isTodayTask(task: MyTask) {
  if (isTaskClosed(task)) return false
  if (task.status === 'running') return true
  if (!task.plan_start) return false
  return dayjs(task.plan_start).isBefore(dayjs().endOf('day')) || dayjs(task.plan_start).isSame(dayjs().endOf('day'))
}

function isTaskClosed(task: MyTask) {
  return ['done', 'completed'].includes(task.status)
}

function isExceptionConfirmTask(task: MyTask) {
  const isProblemStatus = ['blocked', 'interrupted'].includes(task.status)
  const isOverdue = Boolean(task.plan_end) && dayjs(task.plan_end).isBefore(dayjs()) && !isTaskClosed(task)
  const hasDelayReport = Boolean(task.delay_reason) || Boolean(task.delay_hours)
  return isProblemStatus || isOverdue || hasDelayReport
}

function formatTaskTime(value: string | null, fallback: string) {
  return value ? dayjs(value).format('HH:mm') : fallback
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待处理',
    scheduled: '待执行',
    running: '运行中',
    completed: '已完成',
    done: '已完成',
    blocked: '已延期',
    interrupted: '已中断',
  }
  return labels[status] || status
}

function scheduleText(task: MyTask) {
  const startText = formatTaskTime(task.plan_start, '--:--')
  const endText = formatTaskTime(task.plan_end, '--:--')
  return `${startText}–${endText} ${task.task_name || '未命名任务'}`
}

function buildTodayCard(task: MyTask, category: TodayCardCategory): TodayTaskCard {
  const nightStart = formatTaskTime(task.plan_end, DEFAULT_NIGHT_START)
  nightRunRevision.value
  const storedNightRun = readNightRunForm(task)
  const tagTextMap: Record<TodayCardCategory, string> = {
    completion: '完成',
    exception: '异常',
  }
  const tagColorMap: Record<TodayCardCategory, string> = {
    completion: 'green',
    exception: 'red',
  }

  return {
    key: `${category}-${task.slot_id || task.task_id}`,
    category,
    task,
    projectText: task.project_name || task.project_code || '未关联项目',
    taskText: task.task_name || '未命名任务',
    instrumentText: task.instrument_name || task.instrument_code || '未指定仪器',
    ownerText: currentUserName(),
    scheduleText: scheduleText(task),
    tagText: tagTextMap[category],
    tagColor: tagColorMap[category],
    statusText: statusLabel(task.status),
    earliestStart: nightStart,
    latestEnd: NIGHT_RESERVE_END,
    nightRunSummary: storedNightRun ? formatNightRunSummary(storedNightRun) : '',
    delayText: getDelayText(task),
  }
}

function getDelayText(task: MyTask) {
  if (!task.delay_reason && !task.delay_hours) return ''
  const hoursText = task.delay_hours ? `${task.delay_hours}h` : ''
  return [hoursText, task.delay_reason || '未填写原因'].filter(Boolean).join(' · ')
}

function handleCardAction(card: TodayTaskCard, action: string) {
  message.success(`${card.taskText} 已选择：${action}`)
}

function openAutoSequence(card: TodayTaskCard) {
  selectedCard.value = card
  const savedForm = readNightRunForm(card.task)
  setAutoSequenceForm(savedForm || {
    durationHours: DEFAULT_SEQUENCE_DURATION_HOURS,
    earliestStart: card.earliestStart,
    latestEnd: card.latestEnd,
    requiresOperator: false,
    remark: '',
  })
  autoSequenceOpen.value = true
}

function openDelayReport(card: TodayTaskCard) {
  selectedCard.value = card
  delayForm.delayHours = DEFAULT_DELAY_HOURS
  delayForm.reason = ''
  delayReportOpen.value = true
}

async function submitAutoSequence() {
  if (!selectedCard.value) return
  autoSequenceSubmitting.value = true
  try {
    await recordNightRun(selectedCard.value.task.slot_id, {
      duration_hours: autoSequenceForm.durationHours,
      earliest_start: autoSequenceForm.earliestStart,
      latest_end: autoSequenceForm.latestEnd,
      requires_operator: autoSequenceForm.requiresOperator,
      remark: autoSequenceForm.remark.trim() || undefined,
    })
    message.success(`${selectedCard.value.taskText} 已记录为夜间运行`)
    saveNightRunForm(selectedCard.value.task)
    autoSequenceOpen.value = false
    emit('refreshed')
  } catch {
    message.error('夜间运行记录失败')
  } finally {
    autoSequenceSubmitting.value = false
  }
}

function setAutoSequenceForm(form: AutoSequenceForm) {
  autoSequenceForm.durationHours = form.durationHours
  autoSequenceForm.earliestStart = form.earliestStart
  autoSequenceForm.latestEnd = form.latestEnd
  autoSequenceForm.requiresOperator = form.requiresOperator
  autoSequenceForm.remark = form.remark
}

function nightRunStorageKey(task: MyTask) {
  const todayKey = dayjs().format('YYYY-MM-DD')
  const resourceKey = task.instrument_id || task.slot_id
  return `${NIGHT_RUN_STORAGE_PREFIX}:${todayKey}:${task.task_id}:${resourceKey}`
}

function readNightRunForm(task: MyTask): StoredAutoSequenceForm | null {
  try {
    const rawValue = localStorage.getItem(nightRunStorageKey(task))
    if (!rawValue) return null
    const parsedValue = JSON.parse(rawValue) as Partial<StoredAutoSequenceForm>
    if (!parsedValue.durationHours || !parsedValue.earliestStart || !parsedValue.latestEnd) return null
    return {
      durationHours: parsedValue.durationHours,
      earliestStart: parsedValue.earliestStart,
      latestEnd: parsedValue.latestEnd,
      requiresOperator: Boolean(parsedValue.requiresOperator),
      remark: parsedValue.remark || '',
      savedAt: parsedValue.savedAt || dayjs().toISOString(),
    }
  } catch {
    return null
  }
}

function saveNightRunForm(task: MyTask) {
  const storedForm: StoredAutoSequenceForm = {
    durationHours: autoSequenceForm.durationHours,
    earliestStart: autoSequenceForm.earliestStart,
    latestEnd: autoSequenceForm.latestEnd,
    requiresOperator: autoSequenceForm.requiresOperator,
    remark: autoSequenceForm.remark,
    savedAt: dayjs().toISOString(),
  }
  localStorage.setItem(nightRunStorageKey(task), JSON.stringify(storedForm))
  nightRunRevision.value += 1
}

function formatNightRunSummary(form: StoredAutoSequenceForm) {
  const operatorText = form.requiresOperator ? '需人在场启动' : '无需人在场'
  return `今日夜间运行已填写：${form.earliestStart} - ${form.latestEnd}，${form.durationHours}h，${operatorText}`
}

watch(
  autoSequenceForm,
  () => {
    if (!autoSequenceOpen.value || !selectedCard.value) return
    saveNightRunForm(selectedCard.value.task)
  },
  { deep: true },
)

async function submitDelayReport() {
  if (!selectedCard.value) return
  if (!delayForm.reason.trim()) {
    message.warning('请填写异常原因')
    return
  }
  delaySubmitting.value = true
  try {
    const result = await reportTaskDelay(selectedCard.value.task.slot_id, {
      delay_hours: delayForm.delayHours,
      reason: delayForm.reason.trim(),
    })
    message.success(`已顺延排程，影响 ${result.shifted_slots} 个时间槽`)
    delayReportOpen.value = false
    emit('refreshed')
  } catch {
    message.error('异常延期提交失败')
  } finally {
    delaySubmitting.value = false
  }
}
</script>

<style scoped>
.today-work {
  margin-bottom: var(--space-lg);
  padding: var(--space-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.today-work-header {
  margin-bottom: var(--space-md);
}

.today-work-header h3 {
  margin-bottom: 2px;
  color: var(--color-text-primary);
}

.today-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-md);
}

.today-card-group {
  min-width: 0;
  padding: var(--space-sm);
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.today-card-group-title {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.today-card-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--color-accent);
}

.today-card-dot-completion {
  background: var(--color-success);
}

.today-card-dot-exception {
  background: var(--color-danger);
}

.today-card-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.today-card {
  padding: var(--space-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.today-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
  color: var(--color-text-tertiary);
  font-size: 0.78rem;
}

.today-card-lines {
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--color-text-primary);
  font-size: 0.84rem;
  line-height: 1.55;
}

.today-card-lines span {
  color: var(--color-text-secondary);
}

.today-card-choice {
  margin-top: var(--space-sm);
  margin-bottom: var(--space-xs);
  color: var(--color-text-secondary);
  font-size: 0.78rem;
}

.today-card-night-summary {
  margin-bottom: var(--space-xs);
  padding: 6px 8px;
  color: #166534;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  line-height: 1.45;
}

.today-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}

.today-card-empty {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-tertiary);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
}

.modal-task-summary,
.delay-hint {
  margin-bottom: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
}

.delay-hint {
  margin-bottom: 0;
}

.task-action-button-complete {
  color: #ffffff !important;
  background: var(--color-success) !important;
  border-color: var(--color-success) !important;
}
</style>
