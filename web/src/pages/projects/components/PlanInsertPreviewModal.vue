<template>
  <a-modal
    :open="open"
    title="计划调整将产生插单影响"
    width="900px"
    okText="确认按插单排程"
    cancelText="取消"
    :confirmLoading="confirming"
    @ok="emit('confirm')"
    @cancel="emit('cancel')"
  >
    <a-alert
      type="warning"
      showIcon
      message="稳定重排无法满足当前计划"
      :description="`需要顺延 ${movedTaskCount} 个低优先级任务。取消后旧排程保持不变，计划继续标记为待重新排程。`"
      style="margin-bottom: 16px"
    />
    <a-table
      size="small"
      rowKey="task_id"
      :pagination="false"
      :dataSource="result?.impacts || []"
      :columns="columns"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'kind'">
          <a-tag :color="record.is_insert_task ? 'blue' : 'orange'">
            {{ record.is_insert_task ? '当前项目' : '被顺延任务' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'original'">
          {{ formatWindow(record.original_start, record.original_end) }}
        </template>
        <template v-else-if="column.key === 'next'">
          {{ formatWindow(record.new_start, record.new_end) }}
        </template>
        <template v-else-if="column.key === 'delay'">
          <span :class="{ 'delay-positive': record.delay_hours > 0 }">
            {{ record.delay_hours > 0 ? `${record.delay_hours}h` : '-' }}
          </span>
        </template>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { ProjectPlanApplyResult } from '@/types'

interface Props {
  open: boolean
  confirming: boolean
  result: ProjectPlanApplyResult | null
}

const props = defineProps<Props>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const movedTaskCount = computed(() => props.result?.impacts.filter(impact => !impact.is_insert_task).length || 0)
const columns = [
  { title: '类型', key: 'kind', width: 110 },
  { title: '项目', dataIndex: 'project_name', key: 'project', width: 160 },
  { title: '任务', dataIndex: 'task_name', key: 'task', width: 150 },
  { title: '原时间', key: 'original', width: 180 },
  { title: '新时间', key: 'next', width: 180 },
  { title: '延期', key: 'delay', width: 80 },
]

function formatWindow(start: string | null, end: string | null) {
  if (!start || !end) return '未排程'
  return `${dayjs(start).format('MM-DD HH:mm')} – ${dayjs(end).format('MM-DD HH:mm')}`
}
</script>

<style scoped>
.delay-positive { color: var(--color-danger); font-weight: 600; }
</style>