import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from './stores/app'
import http, { cancelByRouteTag } from './api/http'
// 登录页静态导入（不懒加载）：消除路由懒加载对首屏组件挂载的延迟，
// 确保背景图两阶段请求（/api/login-background → new Image() 预加载）在页面打开时即刻发起
import LoginView from './views/LoginView.vue'

const routes = [
  { path: '/login', component: LoginView, meta: { guest: true } },
  { path: '/403', component: () => import('./views/ForbiddenView.vue'), meta: { guest: true } },
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
      quickActionOrder: 1, sidebarOrder: 2, permission: 'admin',
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
    path: '/favorites',
    component: () => import('./views/FavoritesView.vue'),
    meta: {
      titleKey: 'nav.favorites', icon: 'pi pi-star', color: 'var(--warning)',
      showInSidebar: true, sidebarOrder: 4.5,
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
    // 文案存 key，由 AppLayout/QuickActionsCard 的既有 titleKey 机制翻译
    meta: { titleKey: 'announce.detail.route_title' },
  },
  {
    path: '/announce/:announceNo',
    name: 'AnnouncementDetailLegacy',
    component: () => import('./views/LegacyRedirect.vue'),
    meta: { titleKey: 'legacy.redirecting' },
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
  { path: '/scheduler', component: () => import('./views/SchedulerStatus.vue'), meta: {
    titleKey: 'nav.scheduler', icon: 'pi pi-clock', color: 'var(--text-dim)',
    showInSidebar: true, sidebarOrder: 10, permission: 'admin',
  } },
  { path: '/quality', component: () => import('./views/QualityView.vue'), meta: { permission: 'admin' } },
  { path: '/backup', component: () => import('./views/BackupView.vue'), meta: { permission: 'admin' } },
  { path: '/resources', component: () => import('./views/SystemResources.vue'), meta: { permission: 'admin' } },
  { path: '/query-history', component: () => import('./views/QueryHistory.vue'), meta: { permission: 'admin' } },
  { path: '/download-queue', component: () => import('./views/DownloadQueue.vue'), meta: { permission: 'admin' } },
  {
    path: '/download/import',
    component: () => import('./views/DownloadImport.vue'),
    meta: {
      titleKey: 'nav.download_import', icon: 'pi pi-download', color: 'var(--primary)',
      showInSidebar: true, sidebarOrder: 5, permission: 'admin',
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

/** 路由权限判定：只有 meta.permission==='admin' 的路由要求 admin 角色。 */
export function hasRouteAccess(permission: unknown, role: string): boolean {
  return permission !== 'admin' || role === 'admin'
}

/** 首屏导航前补齐身份（硬刷新/登录后 store.username 为空），再判定是否能进目标路由。 */
export async function prepareRoute(meta: Record<string, unknown>, store: {
  username: string
  role: string
  loadPreferences: () => Promise<void>
}): Promise<boolean> {
  if (!store.username) {
    try { await store.loadPreferences() } catch { /* 保持默认角色 */ }
  }
  return hasRouteAccess(meta.permission, store.role)
}

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, from, next) => {
  // 仅跨路由（path 变化）时取消离开路由的请求；同路由 Tab 切换（query 变化、path 不变）
  // 不触发取消，否则会误杀新 Tab onMounted 刚发出的初始化请求
  if (from.path !== to.path) {
    const fromTag = from.matched[from.matched.length - 1]?.path || from.path
    cancelByRouteTag(fromTag)
  }
  if (to.meta.guest) return next()
  const store = useAppStore()
  if (!store.loggedIn) {
    try {
      await http.get('/stats', { skipGlobalAuthRedirect: true })
      store.loggedIn = true
    } catch {
      return next('/login')
    }
  }
  // 首屏异步加载角色：进入任何页面都先补齐身份，避免 / 页面按默认 user 渲染
  // （否则 admin 的 quick action 会在刷新后消失，也会误判 /task 等管理页为 403）
  if (!(await prepareRoute(to.meta, store))) {
    return next('/403')
  }
  return next()
})

export default router
