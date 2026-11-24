// web/src/composables/useAppLayout.test.ts — 应用主布局 composable 单元测试
//
// NEW-44 补齐：此前 `useAppLayout.ts` 无任何测试。本文件锁定**对外行为**（不挂载真实 Layout）：
//   · 初始状态：响应式断点 / 侧边栏默认折叠 / 菜单关闭 / 路由派生值（首页、公告详情）
//   · 导航：navItems 按 showInSidebar / permission / sidebarOrder 生成并走 t() 翻译；pageTitle 回落 PilotStd
//   · 生命周期：onMounted 恢复偏好 + 注册 resize/click；onUnmounted **成对**移除（无泄漏）
//   · 失败路径：偏好保存失败走 console.warn（可观测），不阻断交互；登出接口失败仍清本地状态
//   · 悬浮工作台：拖拽吞点击、按路由态分发、菜单开关与焦点归还、Escape/Tab 无障碍键处理、点外关闭
// 依赖 vue-router / vue-i18n / stores / http / 子 composable 替身；生命周期靠 mount 一个 render-only 宿主触发。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  store: {} as { theme: string; role: string; clearUser: () => void },
  getAll: vi.fn(),
  setPref: vi.fn(),
  post: vi.fn(),
  notifyAuthChanged: vi.fn(),
  t: vi.fn(),
  route: {} as { path: string; params: Record<string, string> },
  getRoutes: vi.fn(),
  push: vi.fn(),
  back: vi.fn(),
  consumeClick: vi.fn(),
  availableCards: { value: [] as unknown[] },
  addCard: vi.fn(),
  resetLayout: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ getRoutes: mocks.getRoutes, push: mocks.push, back: mocks.back }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: mocks.t }) }))
vi.mock('@/stores/app', () => ({ useAppStore: () => mocks.store }))
vi.mock('@/stores/preferences', () => ({
  usePreferencesStore: () => ({ getAll: mocks.getAll, set: mocks.setPref }),
}))
vi.mock('@/composables/useDashboard', () => ({
  useDashboard: () => ({
    availableCards: mocks.availableCards, addCard: mocks.addCard, resetLayout: mocks.resetLayout,
  }),
}))
vi.mock('@/composables/useFloatingDrag', () => ({
  useFloatingDrag: () => ({
    x: { value: 0 }, y: { value: 0 }, onPointerDown: vi.fn(), onPointerMove: vi.fn(),
    onPointerUp: vi.fn(), consumeClick: mocks.consumeClick,
  }),
}))
vi.mock('@/api/http', () => ({
  default: { post: mocks.post },
  notifyAuthChanged: mocks.notifyAuthChanged,
}))

import { useAppLayout } from './useAppLayout'

const I18N: Record<string, string> = { 'nav.home': '首页' }
const ROUTES = [
  { path: '/', meta: { showInSidebar: true, sidebarOrder: 1, titleKey: 'nav.home', icon: 'pi pi-home' } },
  { path: '/standards', meta: { showInSidebar: true, sidebarOrder: 2, title: '标准' } },
  { path: '/admin-only', meta: { showInSidebar: true, sidebarOrder: 3, title: '管理', permission: 'admin' } },
  { path: '/hidden', meta: { showInSidebar: false, title: '隐藏' } },
  { path: '/__action/refresh', meta: { showInSidebar: true, title: '动作' } },
]

let api: ReturnType<typeof useAppLayout>
let wrapper: ReturnType<typeof mount> | undefined

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
}

function mountLayout() {
  wrapper = mount(defineComponent({ setup: () => (api = useAppLayout()), render: () => h('div') }))
  return api
}

describe('useAppLayout', () => {
  beforeEach(() => {
    setViewport(1280)
    mocks.store = reactive({ theme: 'light', role: 'guest', clearUser: vi.fn() })
    mocks.route = reactive({ path: '/', params: {} })
    mocks.getRoutes.mockReset().mockReturnValue(ROUTES)
    mocks.getAll.mockReset().mockResolvedValue({})
    mocks.setPref.mockReset().mockResolvedValue(undefined)
    mocks.post.mockReset().mockResolvedValue({})
    mocks.notifyAuthChanged.mockReset()
    mocks.push.mockReset()
    mocks.back.mockReset()
    mocks.consumeClick.mockReset().mockReturnValue(false)
    mocks.t.mockReset().mockImplementation((key: string) => I18N[key] ?? key)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  it('桌面视口初始状态：断点/侧边栏/菜单/路由派生值/常量 id', async () => {
    mountLayout()
    await flushPromises()

    expect([api.isDesktop.value, api.isTablet.value, api.isMobile.value, api.sidebarCollapsed.value])
      .toEqual([true, false, false, false])
    expect([api.menuOpen.value, api.isHomeRoute.value, api.isAnnounceDetail.value]).toEqual([false, true, false])
    expect([api.triggerBtnId, api.dropdownId]).toEqual(['workspace-menu-trigger', 'workspace-dropdown'])
    expect(api.store).toBe(mocks.store)
  })

  it('平板/移动端默认折叠；resize 更新断点与折叠态（桌面不自动展开）', async () => {
    setViewport(800)
    mountLayout()
    await flushPromises()
    expect([api.isDesktop.value, api.isTablet.value, api.sidebarCollapsed.value]).toEqual([false, true, true])

    setViewport(500)
    window.dispatchEvent(new Event('resize'))
    expect([api.isDesktop.value, api.isMobile.value, api.sidebarCollapsed.value]).toEqual([false, true, true])

    setViewport(1440)
    window.dispatchEvent(new Event('resize'))
    expect([api.isDesktop.value, api.isMobile.value]).toEqual([true, false])
    expect(api.sidebarCollapsed.value).toBe(true)
  })

  it('卸载后移除 resize 监听：再 resize 不再改变断点（无泄漏）', async () => {
    mountLayout()
    await flushPromises()
    wrapper!.unmount()
    wrapper = undefined

    setViewport(500)
    window.dispatchEvent(new Event('resize'))

    expect(api.isDesktop.value).toBe(true)
  })

  it('navItems：按 showInSidebar/permission/order 过滤排序，label 走 titleKey 翻译', () => {
    mountLayout()

    expect(api.navItems.value.map((i) => i.to)).toEqual(['/', '/standards'])
    expect(api.navItems.value.map((i) => i.label)).toEqual(['首页', '标准'])
    expect(api.navItems.value.map((i) => i.icon)).toEqual(['pi pi-home', 'pi pi-circle'])
    expect(api.pageTitle.value).toBe('首页')
  })

  it('navItems：admin 可见全部；role 响应式变化后重算；未知路由 pageTitle 回落 PilotStd', async () => {
    mountLayout()

    mocks.store.role = 'admin'
    await nextTick()
    expect(api.navItems.value.map((i) => i.to)).toEqual(['/', '/standards', '/admin-only'])

    mocks.route.path = '/missing'
    await nextTick()
    expect(api.pageTitle.value).toBe('PilotStd')
  })

  it('挂载时从偏好恢复侧边栏折叠；加载失败保持默认值且不抛异常', async () => {
    mocks.getAll.mockResolvedValueOnce({ sidebar_collapsed: true })
    mountLayout()
    await flushPromises()
    expect(api.sidebarCollapsed.value).toBe(true)
    wrapper!.unmount()
    wrapper = undefined

    setViewport(1280)
    mocks.getAll.mockRejectedValueOnce(new Error('prefs down'))
    expect(() => mountLayout()).not.toThrow()
    await flushPromises()
    expect(api.sidebarCollapsed.value).toBe(false)
  })

  it('toggleSidebar 翻转并持久化；保存失败仅告警、不阻断交互', async () => {
    mountLayout()
    await flushPromises()
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    api.toggleSidebar()
    await flushPromises()
    expect(api.sidebarCollapsed.value).toBe(true)
    expect(mocks.setPref).toHaveBeenCalledWith('sidebar_collapsed', true)

    mocks.setPref.mockRejectedValueOnce(new Error('save failed'))
    api.toggleSidebar()
    await flushPromises()
    expect(api.sidebarCollapsed.value).toBe(false)
    expect(warn).toHaveBeenCalledWith('保存侧边栏偏好失败，只影响下次记忆', expect.any(Error))
  })

  it('toggleTheme 在 light/dark 间切换，isDark 派生同步', () => {
    mountLayout()
    expect(api.isDark.value).toBe(false)

    api.toggleTheme()
    expect([mocks.store.theme, api.isDark.value]).toEqual(['dark', true])
    api.toggleTheme()
    expect([mocks.store.theme, api.isDark.value]).toEqual(['light', false])
  })

  it('logout 成功：广播鉴权变更、清用户、跳登录页', async () => {
    mountLayout()
    await api.logout()

    expect(mocks.post).toHaveBeenCalledWith('/logout', undefined, { skipGlobalAuthRedirect: true })
    expect(mocks.notifyAuthChanged).toHaveBeenCalledTimes(1)
    expect(mocks.store.clearUser).toHaveBeenCalledTimes(1)
    expect(mocks.push).toHaveBeenCalledWith('/login')
  })

  it('logout 失败：服务端错误被吞但本地状态仍清空并跳转（不阻断登出）', async () => {
    mountLayout()
    mocks.post.mockRejectedValueOnce(new Error('network down'))
    await api.logout()

    expect(mocks.notifyAuthChanged).toHaveBeenCalledTimes(1)
    expect(mocks.store.clearUser).toHaveBeenCalledTimes(1)
    expect(mocks.push).toHaveBeenCalledWith('/login')
  })

  it('onFloatingButtonClick：拖拽后吞点击；首页开菜单；详情页返回；其他路由回首页', async () => {
    mountLayout()
    mocks.consumeClick.mockReturnValueOnce(true)
    api.onFloatingButtonClick()
    expect(api.menuOpen.value).toBe(false)

    api.onFloatingButtonClick() // 首页 → 打开工作台菜单
    expect(api.menuOpen.value).toBe(true)

    mocks.route.path = '/detail'
    mocks.route.params = { source: 'gb', announceNo: '2026-1' }
    await nextTick()
    expect(api.isAnnounceDetail.value).toBe(true)
    api.onFloatingButtonClick()
    expect(mocks.back).toHaveBeenCalledTimes(1)

    mocks.route.path = '/standards'
    mocks.route.params = {}
    await nextTick()
    api.onFloatingButtonClick()
    expect(mocks.push).toHaveBeenCalledWith('/')
  })

  it('toggleMenu 打开后焦点移到首项；closeMenu 关闭并把焦点还给触发按钮', async () => {
    mountLayout()
    const trigger = document.createElement('button')
    trigger.id = 'workspace-menu-trigger'
    const menu = document.createElement('div')
    menu.id = 'workspace-dropdown'
    const item = document.createElement('button')
    item.setAttribute('role', 'menuitem')
    menu.appendChild(item)
    document.body.append(trigger, menu)

    api.toggleMenu()
    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(api.menuOpen.value).toBe(true)
    expect(document.activeElement).toBe(item)

    api.closeMenu()
    expect(api.menuOpen.value).toBe(false)
    expect(document.activeElement).toBe(trigger)
  })

  it('onMenuKeydown：Escape 关闭并阻止默认；无菜单项时 Tab 不做处理', () => {
    mountLayout()
    const escape = { key: 'Escape', preventDefault: vi.fn() } as unknown as KeyboardEvent
    api.menuOpen.value = true

    api.onMenuKeydown(escape)
    expect(api.menuOpen.value).toBe(false)
    expect(escape.preventDefault).toHaveBeenCalledTimes(1)

    const tab = { key: 'Tab', preventDefault: vi.fn() } as unknown as KeyboardEvent
    api.onMenuKeydown(tab)
    expect(tab.preventDefault).not.toHaveBeenCalled()
  })

  it('onMenuKeydown：Tab 在首/末可用菜单项之间循环（shift 反向，跳过 aria-disabled）', () => {
    mountLayout()
    const dropdown = document.createElement('div')
    dropdown.id = 'workspace-dropdown'
    const first = document.createElement('button')
    first.setAttribute('role', 'menuitem')
    const disabled = document.createElement('button')
    disabled.setAttribute('role', 'menuitem')
    disabled.setAttribute('aria-disabled', 'true')
    const last = document.createElement('button')
    last.setAttribute('role', 'menuitem')
    dropdown.append(first, disabled, last)
    document.body.appendChild(dropdown)

    first.focus()
    const shiftTab = { key: 'Tab', shiftKey: true, preventDefault: vi.fn() } as unknown as KeyboardEvent
    api.onMenuKeydown(shiftTab)
    expect(shiftTab.preventDefault).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(last)

    const tab = { key: 'Tab', shiftKey: false, preventDefault: vi.fn() } as unknown as KeyboardEvent
    api.onMenuKeydown(tab)
    expect(tab.preventDefault).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(first)
  })

  it('点外关闭菜单、点内保持；卸载后 document click 监听被移除', async () => {
    mountLayout()
    await flushPromises()
    const trigger = document.createElement('button')
    trigger.id = 'workspace-menu-trigger'
    const menu = document.createElement('div')
    menu.className = 'floating-workspace-menu'
    const inner = document.createElement('span')
    menu.appendChild(inner)
    document.body.append(trigger, menu)

    api.menuOpen.value = true
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(api.menuOpen.value).toBe(false)

    api.menuOpen.value = true
    inner.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(api.menuOpen.value).toBe(true)

    wrapper!.unmount()
    wrapper = undefined
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(api.menuOpen.value).toBe(true)
  })

  it('路由切换自动关闭工作台菜单', async () => {
    mountLayout()
    api.menuOpen.value = true

    mocks.route.path = '/standards'
    await nextTick()

    expect(api.menuOpen.value).toBe(false)
  })
})
