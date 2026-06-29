import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from './stores/app'
import axios from 'axios'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { guest: true } },
  { path: '/', component: () => import('./views/HomeView.vue') },
  { path: '/task', component: () => import('./views/TaskView.vue') },
  { path: '/organize', component: () => import('./views/OrganizeView.vue') },
  { path: '/pending', component: () => import('./views/PendingView.vue') },
  { path: '/announce', component: () => import('./views/AnnounceView.vue') },
  { path: '/notification-logs', component: () => import('./views/NotificationLogsView.vue') },
  { path: '/standards-status', component: () => import('./views/StandardsStatusView.vue') },
  { path: '/settings', component: () => import('./views/SettingsView.vue') },
  { path: '/scheduler', component: () => import('./views/SchedulerStatus.vue') },
  { path: '/quality', component: () => import('./views/QualityView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, _from, next) => {
  if (to.meta.guest) return next()
  const store = useAppStore()
  if (store.loggedIn) return next()
  // 页面刷新后 store 丢失状态，用 cookie 验证
  try {
    await axios.get('/api/stats')
    store.loggedIn = true
    next()
  } catch {
    next('/login')
  }
})

export default router
