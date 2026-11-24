// router.test.ts — 路由表结构与权限元数据契约（NEW-44）
//
// router.guard.test.ts 覆盖 hasRouteAccess/prepareRoute 主要分支；本文件锁住**路由表本身**，
// 因为侧边栏/快捷操作/权限都从 meta 派生：
//   · 路径集合完整（误删路由 = 入口消失）；
//   · 访客页 guest 标记、管理页 permission=admin（权限门禁的唯一来源）；
//   · 侧边栏 sidebarOrder 唯一（AppLayout 排序依赖）；
//   · titleKey 在 zh-CN 里真实存在（拼错即侧边栏显示裸 key）；
//   · 登录页静态导入、其余懒加载（首屏背景图两阶段请求的前提）。
import { describe, expect, it } from 'vitest'
import router, { hasRouteAccess, prepareRoute } from './router'
import zhCN from '@/locales/zh-CN.json'

const EXPECTED_PATHS = [
  '/__action/scan_and_index',
  '/',
  '/403',
  '/announce',
  '/announce/:announceNo',
  '/announce/:source/:announceNo',
  '/backup',
  '/download-queue',
  '/download/import',
  '/favorites',
  '/login',
  '/notification-logs',
  '/organize',
  '/pending',
  '/quality',
  '/query-history',
  '/register',
  '/resources',
  '/scheduler',
  '/settings',
  '/standards-status',
  '/task',
]

/** 在 zh-CN 语言包里按点分 key 查值（undefined 即 key 拼错/未翻译） */
function hasLocaleKey(key: string): boolean {
  let node: unknown = zhCN
  for (const part of key.split('.')) {
    if (!node || typeof node !== 'object') return false
    node = (node as Record<string, unknown>)[part]
  }
  return node !== undefined
}

const routes = router.getRoutes()
const find = (path: string) => routes.find((r) => r.path === path)

describe('router 路由表结构', () => {
  it('路径集合完整（新增/删除路由必须同步本清单）', () => {
    expect(routes.map((r) => r.path).sort()).toEqual([...EXPECTED_PATHS].sort())
  })

  it('访客路由带 guest 标记（拦截器据此不查登录态）', () => {
    for (const path of ['/login', '/403', '/register']) {
      const route = find(path)
      expect(route, path).toBeTruthy()
      expect(route!.meta.guest, path).toBe(true)
      expect(route!.meta.permission, path).toBe('guest')
    }
  })

  it('admin-only 路由集合固定；permission 取值只有 admin/user/guest', () => {
    const adminPaths = routes
      .filter((r) => r.meta.permission === 'admin')
      .map((r) => r.path)
      .sort()
    expect(adminPaths).toEqual([
      '/__action/scan_and_index',
      '/backup',
      '/download-queue',
      '/download/import',
      '/quality',
      '/query-history',
      '/resources',
      '/scheduler',
      '/task',
    ])
    for (const route of routes) {
      expect(['admin', 'user', 'guest', undefined], route.path).toContain(route.meta.permission)
    }
  })

  it('侧边栏路由 sidebarOrder 唯一且为正数（AppLayout 排序依赖）', () => {
    const sidebar = routes.filter((r) => r.meta.showInSidebar)
    const orders = sidebar.map((r) => r.meta.sidebarOrder as number)
    expect(sidebar.length).toBe(11)
    expect(new Set(orders).size).toBe(orders.length)
    expect(orders.every((o) => typeof o === 'number' && o > 0)).toBe(true)
  })

  it('侧边栏/快捷操作路由的 titleKey 在 zh-CN 语言包里真实存在', () => {
    const visible = routes.filter((r) => r.meta.showInSidebar || r.meta.showInQuickActions)
    expect(visible.length).toBeGreaterThan(0)
    for (const route of visible) {
      const key = route.meta.titleKey as string
      expect(key, `${route.path} 缺 titleKey`).toBeTruthy()
      expect(hasLocaleKey(key), `${route.path} 的 titleKey「${key}」未翻译`).toBe(true)
    }
  })

  it('登录页静态导入（组件对象），其余页面懒加载（返回 Promise 的工厂）', () => {
    // 首屏背景图两阶段请求依赖 /login 的组件立刻可用，不能被改成 () => import(...)
    expect(typeof find('/login')!.components?.default).toBe('object')
    for (const path of ['/', '/task', '/settings']) {
      expect(typeof find(path)!.components?.default, path).toBe('function')
    }
  })

  it('公告详情两条路由带唯一 name（兼容跳转依赖命名路由）', () => {
    expect(find('/announce/:source/:announceNo')!.name).toBe('AnnouncementDetail')
    expect(find('/announce/:announceNo')!.name).toBe('AnnouncementDetailLegacy')
  })
})

describe('router 权限工具边界（补充 router.guard.test.ts 未覆盖分支）', () => {
  it('hasRouteAccess 只把 admin 视为特权：user/guest/未声明一律放行', () => {
    expect(hasRouteAccess('admin', 'guest')).toBe(false)
    expect(hasRouteAccess('user', 'guest')).toBe(true)
    expect(hasRouteAccess(undefined, 'guest')).toBe(true)
    expect(hasRouteAccess(null, 'user')).toBe(true)
  })

  it('prepareRoute：身份加载失败时普通页仍放行、admin 页抛 identity-unavailable', async () => {
    const store = {
      username: '',
      role: 'user',
      loadPreferences: async () => {
        throw new Error('401')
      },
    }
    await expect(prepareRoute({ permission: 'user' }, store)).resolves.toBe(true)
    await expect(prepareRoute({ permission: 'admin' }, store)).rejects.toThrow('identity-unavailable')
  })
})
