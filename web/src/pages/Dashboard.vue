<template>
  <div>
    <div class="page-header">
      <h2>仪表盘</h2>
    </div>

    <div class="stat-grid">
      <div v-for="(item, i) in stats" :key="i" class="stat-card" :class="{ 'stat-card-clickable': !!item.link }" @click="item.link && router.push(item.link)">
        <div>
          <div class="stat-card-label">{{ item.title }}</div>
          <div class="stat-card-value" :style="item.danger ? { color: '#dc2626' } : {}">{{ item.value }}</div>
          <div v-if="item.suffix" class="stat-card-suffix">{{ item.suffix }}</div>
        </div>
        <div class="stat-card-icon" :style="item.danger ? { background: '#fef2f2', color: '#dc2626' } : {}">
          <component :is="item.icon" />
        </div>
      </div>
    </div>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="14">
        <div class="chart-card">
          <div class="chart-card-header">仪器占用对比</div>
          <div class="chart-card-body">
            <div ref="barChart" style="width: 100%; height: 280px"></div>
          </div>
        </div>
      </a-col>
      <a-col :xs="24" :lg="10">
        <div class="chart-card">
          <div class="chart-card-header">运行时间分布</div>
          <div class="chart-card-body">
            <div ref="pieChart" style="width: 100%; height: 280px"></div>
          </div>
        </div>
      </a-col>
    </a-row>

    <a-card title="仪器利用率详情" style="margin-top: 16px">
      <a-table :dataSource="utilization" :columns="utilColumns" rowKey="instrument_id"
        :pagination="false" size="small" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ExperimentOutlined, ProjectOutlined, ClockCircleOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { getDashboard, getUtilization } from '@/services/api'
import type { DashboardData, UtilizationStats } from '@/types'

const data = ref<DashboardData | null>(null)
const utilization = ref<UtilizationStats[]>([])
const router = useRouter()
const barChart = ref<HTMLElement>()
const pieChart = ref<HTMLElement>()

onMounted(async () => {
  try {
    const [d, u] = await Promise.all([getDashboard(), getUtilization()])
    data.value = d
    utilization.value = u
    renderCharts()
  } catch {
    message.error('加载仪表盘数据失败')
  }
})

function renderCharts() {
  // Simple CSS bar chart
  if (barChart.value && utilization.value.length) {
    const maxH = Math.max(...utilization.value.map(u => u.scheduled_hours + u.actual_run_hours), 1)
    let html = '<div style="display:flex;align-items:flex-end;gap:20px;height:240px;padding:0 20px">'
    utilization.value.forEach((u, i) => {
      const colors = ['#2563eb', '#16a34a', '#7c3aed', '#ea580c', '#0891b2', '#dc2626']
      const p1 = (u.scheduled_hours / maxH * 200) || 4
      const p2 = (u.actual_run_hours / maxH * 200) || 4
      const name = u.instrument_name.length > 6 ? u.instrument_name.slice(0, 6) + '...' : u.instrument_name
      html += `<div style="flex:1;text-align:center">
        <div style="display:flex;gap:4px;justify-content:center;align-items:flex-end;height:210px">
          <div title="计划占用 ${u.scheduled_hours}h" style="width:20px;height:${p1}px;background:${colors[i % 6]};border-radius:4px 4px 0 0;opacity:0.5"></div>
          <div title="实际运行 ${u.actual_run_hours}h" style="width:20px;height:${p2}px;background:${colors[i % 6]};border-radius:4px 4px 0 0"></div>
        </div>
        <div style="font-size:10px;color:#94a3b8;margin-top:4px">${name}</div>
      </div>`
    })
    html += '</div>'
    barChart.value.innerHTML = html
  }

  // Simple SVG pie chart
  if (pieChart.value && utilization.value.length) {
    const total = utilization.value.reduce((s, u) => s + u.actual_run_hours, 0) || 1
    const colors = ['#2563eb', '#16a34a', '#7c3aed', '#ea580c', '#0891b2', '#dc2626']
    let cumulative = 0
    let paths = ''
    utilization.value.forEach((u, i) => {
      const startAngle = (cumulative / total) * Math.PI * 2
      cumulative += u.actual_run_hours
      const endAngle = (cumulative / total) * Math.PI * 2
      const r = 90; const cx = 150; const cy = 150
      const x1 = cx + r * Math.sin(startAngle)
      const y1 = cy - r * Math.cos(startAngle)
      const x2 = cx + r * Math.sin(endAngle)
      const y2 = cy - r * Math.cos(endAngle)
      const large = (endAngle - startAngle) > Math.PI ? 1 : 0
      paths += `<path d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z" fill="${colors[i % 6]}" stroke="#fff" stroke-width="1"/>`
    })
    pieChart.value.innerHTML = `<svg width="300" height="300" viewBox="0 0 300 300">${paths}<circle cx="150" cy="150" r="45" fill="#fff"/></svg>`
  }
}

const utilColumns = [
  { title: '仪器', dataIndex: 'instrument_name', key: 'name' },
  { title: '利用率', dataIndex: 'utilization_rate', key: 'rate' },
  { title: '计划 (h)', dataIndex: 'scheduled_hours', key: 'scheduled' },
  { title: '实际 (h)', dataIndex: 'actual_run_hours', key: 'actual' },
]

const stats = computed(() => [
  { title: '仪器总数', value: data.value?.total_instruments || 0, suffix: '活跃 ' + (data.value?.active_instruments || 0), icon: ExperimentOutlined, danger: false, link: '/projects/resource-ledger' },
  { title: '项目总数', value: data.value?.total_projects || 0, suffix: '活跃 ' + (data.value?.active_projects || 0), icon: ProjectOutlined, danger: false, link: '/projects/ledger' },
  { title: '平均利用率', value: (data.value?.avg_utilization || 0) + '%', suffix: '', icon: ThunderboltOutlined, danger: false },
  { title: '延期任务', value: data.value?.delayed_tasks || 0, suffix: '', icon: ClockCircleOutlined, danger: !!(data.value?.delayed_tasks), link: '/tasks/workspace' },
])
</script>

