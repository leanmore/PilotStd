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
  // 新路由：标准格式 /announce/:source/:announceNo
  {
    path: '/announce/:source/:announceNo',
    name: 'AnnouncementDetail',
    component: () => import('./views/AnnounceDetail.vue'),
    meta: { title: '公告详情' },
  },
  // 兼容路由：旧格式自动重定向
  {
    path: '/announce/:announceNo',
    name: 'AnnouncementDetailLegacy',
    component: () => import('./views/LegacyRedirect.vue'),
    meta: { title: '正在跳转...' },
  },
  { path: '/notification-logs', component: () => import('./views/NotificationLogsView.vue') },
  { path: '/standards-status', component: () => import('./views/StandardsStatusView.vue') },
  { path: '/settings', component: () => import('./views/SettingsView.vue') },
  { path: '/scheduler', component: () => import('./views/SchedulerStatus.vue') },
  { path: '/quality', component: () => import('./views/QualityView.vue') },
  { path: '/backup', component: () => import('./views/BackupView.vue') },
  { path: '/resources', component: () => import('./views/SystemResources.vue') },
  { path: '/query-history', component: () => import('./views/QueryHistory.vue') },
  { path: '/download-queue', component: () => import('./views/DownloadQueue.vue') },
  { path: '/download/import', component: () => import('./views/DownloadImport.vue') },
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
