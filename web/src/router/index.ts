import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'

const routes = [
  {
    path: '/login',
    component: () => import('@/pages/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('@/pages/Dashboard.vue') },
      { path: 'operations/reports', component: () => import('@/pages/operations/DetailedReports.vue') },
      { path: 'operations/project-tasks', component: () => import('@/pages/operations/ProjectTaskDetail.vue') },
      { path: 'operations/lab-status', component: () => import('@/pages/operations/LabStatusScreen.vue') },
      { path: 'kanban/instrument-gantt', component: () => import('@/pages/InstrumentGantt.vue') },
      { path: 'kanban/project-gantt', component: () => import('@/pages/kanban/ProjectGantt.vue') },
      { path: 'kanban/human-gantt', component: () => import('@/pages/kanban/HumanGantt.vue') },
      { path: 'tasks/workspace', component: () => import('@/pages/tasks/PersonalWorkspace.vue') },
      { path: 'tasks/faults', component: () => import('@/pages/tasks/InstrumentFaults.vue') },
      { path: 'projects/ledger', component: () => import('@/pages/ProjectBoard.vue') },
      { path: 'projects/plan-breakdown', component: () => import('@/pages/projects/PlanBreakdown.vue') },
      { path: 'projects/process-dag', component: () => import('@/pages/ProjectDAG.vue') },
      { path: 'projects/resource-ledger', component: () => import('@/pages/projects/ResourceLedger.vue') },
      { path: 'schedule/rules', component: () => import('@/pages/schedule/ScheduleRules.vue') },
      { path: 'schedule/engine', component: () => import('@/pages/ScheduleManager.vue') },
      { path: 'schedule/reschedule', component: () => import('@/pages/schedule/RescheduleAdjust.vue') },
      { path: 'schedule/insert-order', component: () => import('@/pages/schedule/InsertOrder.vue') },
      { path: 'system/alerts', component: () => import('@/pages/system/AlertPush.vue') },
      { path: 'system/external-sync', component: () => import('@/pages/system/ExternalSync.vue') },
      { path: 'system/users', component: () => import('@/pages/system/UserManagement.vue'), meta: { requiresAdmin: true } },
      { path: 'system/basic', component: () => import('@/pages/system/SystemBasic.vue') },
      { path: 'system/calendar', component: () => import('@/pages/system/WorkCalendar.vue') },
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })
const IDLE_TIMEOUT_MS = 30 * 60 * 1000

function clearSession() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  localStorage.removeItem('lastActivityAt')
}

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  const lastActivityAt = Number(localStorage.getItem('lastActivityAt') || Date.now())
  const isIdleExpired = token && Date.now() - lastActivityAt >= IDLE_TIMEOUT_MS
  if (isIdleExpired) {
    clearSession()
    next('/login?expired=1')
    return
  }
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.requiresAdmin && getStoredUserRole() !== '系统管理员') {
    next('/dashboard')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

function getStoredUserRole() {
  const raw = localStorage.getItem('user')
  if (!raw) return ''
  try {
    const parsed = JSON.parse(raw) as { role?: unknown }
    return typeof parsed.role === 'string' ? parsed.role : ''
  } catch {
    return ''
  }
}

export default router
