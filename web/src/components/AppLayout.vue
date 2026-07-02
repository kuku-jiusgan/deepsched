<template>
  <a-layout style="min-height: 100vh; background: #f7f8fa">
    <a-layout-sider width="220" style="background: #1a1a2e; border-right: none; display: flex; flex-direction: column; overflow: hidden">
      <div style="height: 56px; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid rgba(255,255,255,0.06)">
        <span style="color: #fff; font-size: 15px; font-weight: 600; letter-spacing: 0.5px">DeepSched</span>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="[route.path]"
        :default-open-keys="openKeys"
        :items="menuItems"
        style="background: transparent; border-right: none; margin-top: 8px; flex: 1; overflow-y: auto; overflow-x: hidden"
        @click="navigate"
      />

      <div style="padding: 12px; border-top: 1px solid rgba(255,255,255,0.06); flex-shrink: 0">
        <a-button type="text" block @click="handleLogout" style="color: rgba(255,255,255,0.65); text-align: left">
          <template #icon><LogoutOutlined /></template>
          退出登录
        </a-button>
      </div>
    </a-layout-sider>
    <a-layout style="background: #f7f8fa">
      <a-layout-content style="margin: 20px; padding: 24px; background: #fff; border-radius: 10px; overflow: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.04)">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  FundOutlined, AppstoreOutlined, CheckSquareOutlined,
  ProjectOutlined, ScheduleOutlined, SettingOutlined,
  DashboardOutlined, FileTextOutlined, DesktopOutlined,
  BarChartOutlined, UserOutlined, MessageOutlined,
  WarningOutlined, DatabaseOutlined, PartitionOutlined,
  ApartmentOutlined, TableOutlined, ToolOutlined,
  ThunderboltOutlined, SwapOutlined, DollarOutlined,
  BellOutlined, SyncOutlined, TeamOutlined, LogoutOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()

const iconMap: Record<string, any> = {
  FundOutlined, AppstoreOutlined, CheckSquareOutlined,
  ProjectOutlined, ScheduleOutlined, SettingOutlined,
  DashboardOutlined, FileTextOutlined, DesktopOutlined,
  BarChartOutlined, UserOutlined, MessageOutlined,
  WarningOutlined, DatabaseOutlined, PartitionOutlined,
  ApartmentOutlined, TableOutlined, ToolOutlined,
  ThunderboltOutlined, SwapOutlined, DollarOutlined,
  BellOutlined, SyncOutlined, TeamOutlined, LogoutOutlined,
}

function icon(name: string) {
  return () => h(iconMap[name])
}

const menuItems = [
  { key: '/operations', icon: icon('FundOutlined'), label: '运营数据中台', children: [
    { key: '/dashboard', icon: icon('DashboardOutlined'), label: '核心 KPI 仪表盘' },
    { key: '/operations/reports', icon: icon('FileTextOutlined'), label: '精细化运营报表' },
    { key: '/operations/lab-status', icon: icon('DesktopOutlined'), label: '实验室状态大屏' },
  ]},
  { key: '/kanban', icon: icon('AppstoreOutlined'), label: '交互式看板', children: [
    { key: '/kanban/instrument-gantt', icon: icon('BarChartOutlined'), label: '仪器甘特图' },
    { key: '/kanban/project-gantt', icon: icon('BarChartOutlined'), label: '项目甘特图' },
  ]},
  { key: '/tasks', icon: icon('CheckSquareOutlined'), label: '任务管理', children: [
    { key: '/tasks/workspace', icon: icon('UserOutlined'), label: '个人工作台' },
  ]},
  { key: '/projects', icon: icon('ProjectOutlined'), label: '项目管理', children: [
    { key: '/projects/ledger', icon: icon('DatabaseOutlined'), label: '项目台账管理' },
    { key: '/projects/plan-breakdown', icon: icon('PartitionOutlined'), label: '项目计划拆解' },
    { key: '/projects/process-dag', icon: icon('ApartmentOutlined'), label: '标准工序依赖配置' },
    { key: '/projects/resource-ledger', icon: icon('TableOutlined'), label: '基础资源台账' },
  ]},
  { key: '/schedule', icon: icon('ScheduleOutlined'), label: '排程管理', children: [
    { key: '/schedule/rules', icon: icon('ToolOutlined'), label: '排程规则配置' },
    { key: '/schedule/engine', icon: icon('ThunderboltOutlined'), label: '自动排程引擎' },
    { key: '/schedule/reschedule', icon: icon('SwapOutlined'), label: '重排与人工微调' },
    { key: '/schedule/insert-order', icon: icon('DollarOutlined'), label: '插单与代价计算' },
  ]},
  { key: '/system', icon: icon('SettingOutlined'), label: '系统管理', children: [
    { key: '/system/alerts', icon: icon('BellOutlined'), label: '智能预警推送' },
    { key: '/system/external-sync', icon: icon('SyncOutlined'), label: '外部数据同步' },
    { key: '/system/users', icon: icon('TeamOutlined'), label: '用户管理' },
    { key: '/system/basic', icon: icon('SettingOutlined'), label: '系统基础管理' },
  ]},
]

const openKeys = computed(() => {
  for (const item of menuItems) {
    if (item.children?.some((c: any) => c.key === route.path)) {
      return [item.key]
    }
  }
  return []
})

function handleLogout() { localStorage.removeItem('token'); localStorage.removeItem('user'); router.replace('/login') }

function navigate({ key }: { key: string }) {
  router.push(key)
}
</script>

