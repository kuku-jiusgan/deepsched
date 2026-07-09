<template>
  <a-layout style="min-height: 100vh; background: #f7f8fa">
    <a-layout-sider width="220" style="background: #1a1a2e; border-right: none; display: flex; flex-direction: column; overflow: hidden">
      <div style="height: 130px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.06)">
        <img src="/公司logo.png" style="height: 48px; margin-bottom: 10px" />
        <span style="color: #fff; font-size: 15px; font-weight: 700; letter-spacing: 1.5px">仪器与项目智能调度管理平台</span>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="[route.path]"
        :default-open-keys="openKeys"
        :items="menuItems"
        style="background: transparent; border-right: none; margin-top: 20px; flex: 1; overflow-y: auto; overflow-x: hidden"
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
      <a-layout-content class="app-content">
        <div class="page-top-actions">
          <a-tag color="blue" class="current-user">
            <UserOutlined />
            <span>{{ currentUserLabel }}</span>
          </a-tag>
        <a-popover v-model:open="notificationOpen" trigger="click" placement="bottomRight" overlayClassName="notification-popover">
          <template #content>
            <div class="notification-panel">
              <div class="notification-panel-head">
                <span>站内通知</span>
                <a-button type="link" size="small" @click="fetchNotifications">刷新</a-button>
              </div>
              <a-empty v-if="notifications.length === 0" :image="Empty.PRESENTED_IMAGE_SIMPLE" description="暂无未读通知" />
              <div v-else class="notification-list">
                <div
                  v-for="item in notifications"
                  :key="item.id"
                  class="notification-item"
                  @click="readNotification(item)"
                >
                  <div class="notification-item-head">
                    <a-tag :color="notificationTypeColor(item.n_type)">{{ notificationTypeLabel(item.n_type) }}</a-tag>
                    <span>{{ formatTime(item.created_at) }}</span>
                  </div>
                  <div class="notification-title">{{ item.title || '系统通知' }}</div>
                  <div class="notification-content">{{ item.content || '-' }}</div>
                  <div v-if="item.is_confirmed === false" class="notification-actions">
                    <a-button size="small" type="primary" @click.stop="confirmItem(item)">确认</a-button>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <a-badge :count="unreadCount" :overflow-count="99" size="small">
            <a-button class="notification-button" shape="circle">
              <template #icon><BellOutlined /></template>
            </a-button>
          </a-badge>
        </a-popover>
        </div>
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Empty, message } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  FundOutlined, AppstoreOutlined, CheckSquareOutlined,
  ProjectOutlined, ScheduleOutlined, SettingOutlined,
  DashboardOutlined, FileTextOutlined, DesktopOutlined,
  BarChartOutlined, UserOutlined, MessageOutlined,
  WarningOutlined, DatabaseOutlined, PartitionOutlined,
  ApartmentOutlined, TableOutlined, ToolOutlined,
  ThunderboltOutlined, SwapOutlined, DollarOutlined,
  BellOutlined, SyncOutlined, TeamOutlined, CalendarOutlined, LogoutOutlined,
} from '@ant-design/icons-vue'
import {
  confirmNotification,
  getNotifications,
  markNotificationRead,
  type NotificationRecord,
} from '@/services/api'

const router = useRouter()
const route = useRoute()
const notificationOpen = ref(false)
const notifications = ref<NotificationRecord[]>([])
let notificationTimer: number | undefined

const iconMap: Record<string, any> = {
  FundOutlined, AppstoreOutlined, CheckSquareOutlined,
  ProjectOutlined, ScheduleOutlined, SettingOutlined,
  DashboardOutlined, FileTextOutlined, DesktopOutlined,
  BarChartOutlined, UserOutlined, MessageOutlined,
  WarningOutlined, DatabaseOutlined, PartitionOutlined,
  ApartmentOutlined, TableOutlined, ToolOutlined,
  ThunderboltOutlined, SwapOutlined, DollarOutlined,
  BellOutlined, SyncOutlined, TeamOutlined, CalendarOutlined, LogoutOutlined,
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
    { key: '/tasks/faults', icon: icon('ToolOutlined'), label: '故障提报' },
  ]},
  { key: '/projects', icon: icon('ProjectOutlined'), label: '项目管理', children: [
    { key: '/projects/ledger', icon: icon('DatabaseOutlined'), label: '项目台账管理' },
    { key: '/projects/plan-breakdown', icon: icon('PartitionOutlined'), label: '项目计划拆解' },
    { key: '/projects/process-dag', icon: icon('ApartmentOutlined'), label: '标准工序依赖配置' },
    { key: '/projects/resource-ledger', icon: icon('TableOutlined'), label: '仪器基础信息' },
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
    { key: '/system/calendar', icon: icon('CalendarOutlined'), label: '工作日历管理' },
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

const unreadCount = computed(() => notifications.value.filter(item => !item.is_read).length)
const currentUserLabel = computed(() => {
  const user = getStoredUser()
  return user?.display_name || user?.username || '未登录'
})

function handleLogout() {
  if (notificationTimer) window.clearInterval(notificationTimer)
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.replace('/login')
}

function navigate({ key }: { key: string }) {
  router.push(key)
}

async function fetchNotifications() {
  const user = getStoredUser()
  if (!user?.username) return
  try {
    notifications.value = await getNotifications({
      user_name: user.username,
      channel: 'site',
      unread_only: true,
    })
  } catch {
    message.error('站内通知加载失败')
  }
}

async function readNotification(item: NotificationRecord) {
  if (item.is_confirmed === false) return
  await markNotificationRead(item.id)
  notifications.value = notifications.value.filter(n => n.id !== item.id)
}

async function confirmItem(item: NotificationRecord) {
  await confirmNotification(item.id)
  await markNotificationRead(item.id)
  notifications.value = notifications.value.filter(n => n.id !== item.id)
  message.success('已确认')
}

function getStoredUser(): { username: string; display_name?: string } | null {
  const raw = localStorage.getItem('user')
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as { username?: unknown; display_name?: unknown }
    if (typeof parsed.username !== 'string') return null
    return {
      username: parsed.username,
      display_name: typeof parsed.display_name === 'string' ? parsed.display_name : undefined,
    }
  } catch {
    return null
  }
}

function formatTime(value: string) {
  return dayjs(value).format('MM-DD HH:mm')
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

onMounted(() => {
  fetchNotifications()
  notificationTimer = window.setInterval(fetchNotifications, 15000)
})

onBeforeUnmount(() => {
  if (notificationTimer) window.clearInterval(notificationTimer)
})
</script>

<style scoped>
.app-content {
  position: relative;
  margin: 20px;
  padding: 24px;
  background: var(--color-surface);
  border-radius: 10px;
  overflow: auto;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.page-top-actions {
  position: absolute;
  top: 18px;
  right: 24px;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 10px;
}

.current-user {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  margin-right: 0;
  line-height: 30px;
}

.notification-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.notification-panel {
  width: 360px;
  max-width: calc(100vw - 48px);
}

.notification-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border-light);
  font-weight: 600;
  color: var(--color-text-primary);
}

.notification-list {
  max-height: 420px;
  overflow: auto;
  padding-top: 8px;
}

.notification-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-light);
  cursor: pointer;
}

.notification-item:last-child {
  border-bottom: none;
}

.notification-item:hover .notification-title {
  color: var(--color-accent);
}

.notification-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.75rem;
  color: var(--color-text-tertiary);
}

.notification-title {
  margin-top: 6px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-primary);
}

.notification-content {
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notification-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>

