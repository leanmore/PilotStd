// web/src/views/__tests__/HomeView.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import HomeView from '@/views/HomeView.vue'
import http from '@/api/http'
import zhCN from '@/locales/zh-CN.json'

vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

// 共享 mock 状态，测试中可随意修改
const { mockStore } = vi.hoisted(() => ({
  mockStore: {
    loggedIn: true,
    userId: 1,
    dashboardLocked: true,
    toggleDashboardLock() {
      mockStore.dashboardLocked = !mockStore.dashboardLocked
    },
  },
}))

vi.mock('@/stores/app', () => ({ useAppStore: () => mockStore }))

vi.mock('grid-layout-plus', () => ({
  GridLayout: { name: 'GridLayout', template: '<div class="mock-grid"><slot /></div>', props: ['layout', 'colNum', 'rowHeight', 'isDraggable', 'isResizable', 'verticalCompact', 'useCssTransforms', 'margin'], emits: ['update:layout', 'layout-updated'] },
  GridItem: { name: 'GridItem', template: '<div class="mock-grid-item"><slot /></div>', props: ['i', 'x', 'y', 'w', 'h', 'minW', 'minH'] },
}))

// Mock 子卡片组件（内联工厂，避免 vi.mock 提升问题）
vi.mock('@/components/dashboard/widgets/StatsCard.vue', () => ({ default: { name: 'StatsCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/SystemInfoCard.vue', () => ({ default: { name: 'SystemInfoCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/QuickActionsCard.vue', () => ({ default: { name: 'QuickActionsCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue', () => ({ default: { name: 'AnnounceCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/AdapterStatusQueryCard.vue', () => ({ default: { name: 'QueryCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/RecentAnnounceCard.vue', () => ({ default: { name: 'RecentCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/PendingItemsCard.vue', () => ({ default: { name: 'PendingCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/TaskTrendCard.vue', () => ({ default: { name: 'TrendCard', template: '<div class="stub" />' } }))
vi.mock('@/components/dashboard/widgets/SystemLogCard.vue', () => ({ default: { name: 'LogCard', template: '<div class="stub" />' } }))

function mountHome() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(HomeView, { global: { plugins: [pinia, i18n] } })
}

describe('HomeView 布局与持久化', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始化：解析后端布局数组并渲染卡片', async () => {
    const mockLayout = [{ i: 'stats', x: 0, y: 0, w: 4, h: 6 }]
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: mockLayout } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(http.get).toHaveBeenCalledWith('/user/preferences/layout:dashboard', { routeTag: '/' })
    expect(wrapper.vm.layout.length).toBe(1)
    expect(wrapper.vm.layout[0].i).toBe('stats')
  })

  it('初始化：后端返回空数组时加载默认 5 张卡片', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: [] } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(wrapper.vm.layout.length).toBe(5)
  })

  it('初始化：后端返回 null 时降级到默认布局', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: null } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(wrapper.vm.layout.length).toBe(5)
  })

  it('初始化：网络异常时降级到默认布局不报错', async () => {
    vi.mocked(http.get).mockRejectedValueOnce(new Error('Network Error'))

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(wrapper.vm.layout.length).toBe(5)
  })

  it('锁定：默认锁定，GridLayout 不可拖拽不可缩放', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: [] } })
    mockStore.dashboardLocked = true
    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    const grid = wrapper.findComponent({ name: 'GridLayout' })
    expect(grid.props('isDraggable')).toBe(false)
    expect(grid.props('isResizable')).toBe(false)
  })

  it('解锁：dashboardLocked=false 后 GridLayout 可拖拽可缩放', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: [] } })
    mockStore.dashboardLocked = false
    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    const grid = wrapper.findComponent({ name: 'GridLayout' })
    expect(grid.props('isDraggable')).toBe(true)
    expect(grid.props('isResizable')).toBe(true)
  })

  it('持久化：layout-updated 后防抖 500ms 才发 PUT', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: [] } })
    vi.mocked(http.put).mockResolvedValueOnce({})

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    const grid = wrapper.findComponent({ name: 'GridLayout' })
    const newLayout = wrapper.vm.layout.map((l: any) => ({ i: l.i, x: 0, y: 0, w: l.w, h: l.h }))
    grid.vm.$emit('update:layout', newLayout)

    // 立即：不应发请求
    expect(http.put).not.toHaveBeenCalled()

    // 快进 500ms
    await vi.advanceTimersByTimeAsync(500)

    expect(http.put).toHaveBeenCalledTimes(1)
    const [url, body] = vi.mocked(http.put).mock.calls[0] as [string, any]
    expect(url).toBe('/user/preferences/layout:dashboard')
    // body 不含 component 实例
    const parsed = body.value
    expect(parsed[0]).not.toHaveProperty('component')
    expect(parsed[0]).toHaveProperty('i')
    expect(parsed[0]).toHaveProperty('x')
  })

  it('Payload：PUT 格式严格为 {value: [...]}', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: [] } })
    vi.mocked(http.put).mockResolvedValueOnce({})

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    const testLayout = wrapper.vm.layout.map((l: any) => ({ i: l.i, x: 0, y: 0, w: l.w, h: l.h }))
    const grid = wrapper.findComponent({ name: 'GridLayout' })
    grid.vm.$emit('update:layout', testLayout)
    await vi.advanceTimersByTimeAsync(500)

    const body = (vi.mocked(http.put).mock.calls[0] as any)[1]
    expect(body).toHaveProperty('value')
    expect(body.value).toBeInstanceOf(Array)
  })

  it('初始化：迁移旧 localStorage key 到用户隔离格式', async () => {
    // 模拟 PR-B 部署前已登录用户 —— localStorage 中有旧裸 key
    localStorage.setItem('dashboard_layout', JSON.stringify([{ i: 'stats', x: 0, y: 0, w: 4, h: 6 }]))
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: null } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    // 旧 key 应被删除，新 key 应存在
    expect(localStorage.getItem('dashboard_layout')).toBeNull()
    expect(localStorage.getItem('user_1_dashboard_layout')).not.toBeNull()
    // 新 key 中的布局数据应被正确加载
    expect(wrapper.vm.layout.length).toBe(1)
    expect(wrapper.vm.layout[0].i).toBe('stats')
  })

  it('初始化：幂等——新 key 已存在时跳过迁移', async () => {
    // 新 key 已存在
    localStorage.setItem('user_1_dashboard_layout', JSON.stringify([{ i: 'sysInfo', x: 0, y: 0, w: 4, h: 6 }]))
    // 旧 key 也有（模拟残留）
    localStorage.setItem('dashboard_layout', JSON.stringify([{ i: 'stats', x: 0, y: 0, w: 4, h: 6 }]))
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: null } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    // 使用的是新 key 的数据（sysInfo），旧 key 数据未被使用
    expect(wrapper.vm.layout.length).toBe(1)
    expect(wrapper.vm.layout[0].i).toBe('sysInfo')
  })
})
