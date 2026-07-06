<template>
  <div>
    <div class="page-header"><h2>工作日历管理</h2></div>

    <div class="action-bar">
      <a-space>
        <a-button @click="prevMonth"><LeftOutlined /></a-button>
        <span style="font-weight: 600; font-size: 15px; min-width: 120px; text-align: center">{{ viewYear }}年{{ viewMonth }}月</span>
        <a-button @click="nextMonth"><RightOutlined /></a-button>
        <a-button @click="goToday">本月</a-button>
      </a-space>
      <a-button @click="handleBatchFill" :loading="filling" size="small">预填充 {{ viewYear }} 年</a-button>
      <a-button @click="handleSync" :loading="syncing" type="primary" ghost size="small">同步 {{ viewYear }} 年节假日</a-button>
      <span style="margin-left: auto; font-size: 12px; color: #94a3b8">
        工作日 {{ workdayCount }} · 非工作日 {{ nonWorkdayCount }}
      </span>
    </div>

    <a-spin v-if="loading" size="large" style="display: block; margin: 50px auto" />

    <div v-else class="calendar-grid">
      <div class="cal-header" v-for="d in weekDays" :key="d">{{ d }}</div>
      <div v-for="(cell, idx) in calendarCells" :key="idx"
        class="cal-cell"
        :class="{
          'cal-other': !cell.inMonth,
          'cal-today': cell.isToday,
          'cal-workday': cell.inMonth && cell.isWorkingDay && cell.dayType === 'workday',
          'cal-weekend': cell.inMonth && !cell.isWorkingDay && cell.dayType === 'weekend',
          'cal-holiday': cell.inMonth && !cell.isWorkingDay && cell.dayType === 'holiday',
          'cal-compensate': cell.inMonth && cell.isWorkingDay && cell.dayType === 'compensate',
        }"
        @click="cell.inMonth && toggleCell(cell)">
        <div class="cal-date">{{ cell.day }}</div>
        <div v-if="cell.inMonth" class="cal-tag">
          <a-tag v-if="cell.dayType === 'holiday'" color="red" style="font-size: 10px; line-height: 16px; margin: 0">{{ cell.holidayName || '假日' }}</a-tag>
          <a-tag v-else-if="cell.dayType === 'compensate'" color="orange" style="font-size: 10px; line-height: 16px; margin: 0">调休</a-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined } from '@ant-design/icons-vue'
import { getCalendar, upsertCalendarDate, batchFillCalendar, syncHolidays, type CalendarDay } from '@/services/api'

interface CalCell {
  date: string; day: number; inMonth: boolean; isToday: boolean
  isWorkingDay: boolean; dayType: string; holidayName: string; id: number | null
}

const loading = ref(true)
const filling = ref(false)
const syncing = ref(false)
const calData = ref<CalendarDay[]>([])
const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth() + 1)

const weekDays = ['日', '一', '二', '三', '四', '五', '六']

const calendarCells = computed<CalCell[]>(() => {
  const cells: CalCell[] = []
  const firstDay = new Date(viewYear.value, viewMonth.value - 1, 1)
  const lastDay = new Date(viewYear.value, viewMonth.value, 0)
  const startDow = firstDay.getDay()
  const todayStr = now.toISOString().slice(0, 10)

  // Previous month fill
  const prevLast = new Date(viewYear.value, viewMonth.value - 1, 0)
  for (let i = startDow - 1; i >= 0; i--) {
    const d = prevLast.getDate() - i
    const ds = `${viewYear.value}-${String(viewMonth.value - 1 || 12).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ date: ds, day: d, inMonth: false, isToday: ds === todayStr, isWorkingDay: true, dayType: 'workday', holidayName: '', id: null })
  }

  // Current month
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const ds = `${viewYear.value}-${String(viewMonth.value).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const found = calData.value.find(c => c.date === ds)
    cells.push({
      date: ds, day: d, inMonth: true, isToday: ds === todayStr,
      isWorkingDay: found ? found.is_working_day : (new Date(ds).getDay() % 6 !== 0),
      dayType: found ? found.day_type : (new Date(ds).getDay() % 6 !== 0 ? 'workday' : 'weekend'),
      holidayName: found?.holiday_name || '',
      id: found?.id || null
    })
  }

  // Next month fill
  const remaining = 7 - (cells.length % 7)
  if (remaining < 7) {
    for (let d = 1; d <= remaining; d++) {
      const ds = `${viewYear.value}-${String(viewMonth.value + 1 || 12).padStart(2, '0')}-${String(d).padStart(2, '0')}`
      cells.push({ date: ds, day: d, inMonth: false, isToday: ds === todayStr, isWorkingDay: true, dayType: 'workday', holidayName: '', id: null })
    }
  }

  return cells
})

const workdayCount = computed(() => calendarCells.value.filter(c => c.inMonth && c.isWorkingDay).length)
const nonWorkdayCount = computed(() => calendarCells.value.filter(c => c.inMonth && !c.isWorkingDay).length)

function prevMonth() {
  if (viewMonth.value === 1) { viewYear.value--; viewMonth.value = 12 }
  else viewMonth.value--
  fetchData()
}
function nextMonth() {
  if (viewMonth.value === 12) { viewYear.value++; viewMonth.value = 1 }
  else viewMonth.value++
  fetchData()
}
function goToday() {
  viewYear.value = now.getFullYear(); viewMonth.value = now.getMonth() + 1
  fetchData()
}

async function toggleCell(cell: CalCell) {
  const newWork = !cell.isWorkingDay
  const newType = newWork
    ? (new Date(cell.date).getDay() % 6 === 0 ? 'compensate' : 'workday')
    : (cell.dayType === 'compensate' ? 'weekend' : 'holiday')
  try {
    await upsertCalendarDate(cell.date, { is_working_day: newWork, day_type: newType })
    cell.isWorkingDay = newWork
    cell.dayType = newType
    message.success(`${cell.date} 已${newWork ? '设为工作日' : '设为非工作日'}`)
  } catch { message.error('更新失败') }
}

async function fetchData() {
  loading.value = true
  try {
    calData.value = await getCalendar(viewYear.value, viewMonth.value)
  } catch { message.error('加载日历失败') }
  finally { loading.value = false }
}

async function handleBatchFill() {
  filling.value = true
  try {
    const r = await batchFillCalendar(viewYear.value)
    message.success(r.detail || '填充完成')
    await fetchData()
  } catch { message.error('填充失败') }
  finally { filling.value = false }
}

async function handleSync() {
  syncing.value = true
  try {
    const r = await syncHolidays(viewYear.value)
    message.success(r.detail || '同步完成')
    await fetchData()
  } catch (e: any) { message.error(e?.response?.data?.detail || '同步失败') }
  finally { syncing.value = false }
}

onMounted(() => { fetchData() })
</script>

<style scoped>
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  margin-top: 12px;
}
.cal-header {
  text-align: center;
  padding: 10px 0;
  font-weight: 600;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border-bottom: 2px solid #e5e7eb;
}
.cal-cell {
  min-height: 80px;
  padding: 6px 8px;
  border-right: 1px solid #f1f5f9;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}
.cal-cell:nth-child(7n) { border-right: none; }
.cal-cell:hover { background: #eff6ff; }
.cal-other { opacity: 0.35; cursor: default; }
.cal-other:hover { background: transparent; }
.cal-today { box-shadow: inset 0 0 0 2px #3b82f6; }
.cal-today .cal-date { color: #3b82f6; font-weight: 700; }
.cal-workday { background: #fff; }
.cal-weekend { background: #f8fafc; }
.cal-holiday { background: #fef2f2; }
.cal-compensate { background: #fff7ed; }
.cal-date { font-size: 14px; font-weight: 500; color: #1e293b; }
.cal-weekend .cal-date { color: #94a3b8; }
.cal-holiday .cal-date { color: #dc2626; }
.cal-compensate .cal-date { color: #ea580c; }
.cal-tag { margin-top: 2px; }
</style>
