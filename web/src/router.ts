import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from './stores/app'
import { cancelAllRequests } from './api/http'
import axios from 'axios'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { guest: true } },
  { path: '/register', component: () => import('./views/RegisterView.vue'), meta: { guest: true } },
  {
    path: '/',
    component: () => import('./views/HomeView.vue'),
    meta: {
      titleKey: 'nav.home', icon: 'pi pi-home', color: 'var(--primary)',
      showInSidebar: true, sidebarOrder: 1,
    },
  },
  {
    path: '/task',
    component: () => import('./views/TaskView.vue'),
    meta: {
      titleKey: 'nav.task', icon: 'pi pi-play', color: 'var(--primary)',
      showInSidebar: true, showInQuickActions: true, quickActionType: 'navigation',
      quickActionOrder: 1, sidebarOrder: 2,
    },
  },
  {
    path: '/organize',
    component: () => import('./views/OrganizeView.vue'),
    meta: {
      titleKey: 'nav.organize', icon: 'pi pi-folder', color: 'var(--warning)',
      showInSidebar: true, showInQuickActions: true, quickActionType: 'navigation',
      quickActionOrder: 2, sidebarOrder: 3,
    },
  },
  {
    path: '/pending',
    component: () => import('./views/PendingView.vue'),
    meta: {
      titleKey: 'nav.pending', icon: 'pi pi-hourglass', color: 'var(--info)',
      showInSidebar: true, showInQuickActions: true, quickActionType: 'navigation',
      quickActionOrder: 3, sidebarOrder: 4,
    },
  },
  {
    path: '/announce',
    component: () => import('./views/AnnounceView.vue'),
    meta: {
      titleKey: 'nav.announce', icon: 'pi pi-megaphone', color: 'var(--success)',
      showInSidebar: true, showInQuickActions: true, quickActionType: 'navigation',
      quickActionOrder: 4, sidebarOrder: 6,
    },
  },
  {
    path: '/announce/:source/:announceNo',
    name: 'AnnouncementDetail',
    component: () => import('./views/AnnounceDetail.vue'),
    meta: { title: '公告详情' },
  },
  {
    path: '/announce/:announceNo',
    name: 'AnnouncementDetailLegacy',
    component: () => import('./views/LegacyRedirect.vue'),
    meta: { title: '正在跳转...' },
  },
  {
    path: '/notification-logs',
    component: () => import('./views/NotificationLogsView.vue'),
    meta: {
      titleKey: 'nav.notification_logs', icon: 'pi pi-list', color: 'var(--warning)',
      showInSidebar: true, sidebarOrder: 7,
    },
  },
  {
    path: '/standards-status',
    component: () => import('./views/StandardsStatusView.vue'),
    meta: {
      titleKey: 'nav.standards_status', icon: 'pi pi-verified', color: 'var(--info)',
      showInSidebar: true, sidebarOrder: 8,
    },
  },
  {
    path: '/settings',
    component: () => import('./views/SettingsView.vue'),
    meta: {
      titleKey: 'nav.settings', icon: 'pi pi-cog', color: 'var(--text-dim)',
      showInSidebar: true, permission: 'user', sidebarOrder: 9,
    },
  },
  { path: '/scheduler', component: () => import('./views/SchedulerStatus.vue') },
  { path: '/quality', component: () => import('./views/QualityView.vue') },
  { path: '/backup', component: () => import('./views/BackupView.vue') },
  { path: '/resources', component: () => import('./views/SystemResources.vue') },
  { path: '/query-history', component: () => import('./views/QueryHistory.vue') },
  { path: '/download-queue', component: () => import('./views/DownloadQueue.vue') },
  {
    path: '/download/import',
    component: () => import('./views/DownloadImport.vue'),
    meta: {
      titleKey: 'nav.download_import', icon: 'pi pi-download', color: 'var(--primary)',
      showInSidebar: true, sidebarOrder: 5,
    },
  },
  // #49 虚拟路由：动作型快捷操作（不渲染到侧边栏，不在 URL 中可访问）
  {
    path: '/__action/scan_and_index',
    component: { template: '<div></div>' },
    meta: {
      titleKey: 'action.scan_index', icon: 'pi pi-cloud-upload', color: '#ec4899',
      showInSidebar: false, showInQuickActions: true, quickActionType: 'action',
      handler: 'scanAndIndex', permission: 'admin', quickActionOrder: 5,
    },
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, _from, next) => {
  cancelAllRequests()
  if (to.meta.guest) return next()
  const store = useAppStore()
  if (store.loggedIn) return next()
  try {
    await axios.get('/api/stats')
    store.loggedIn = true
    next()
  } catch {
    next('/login')
  }
})

export default router
