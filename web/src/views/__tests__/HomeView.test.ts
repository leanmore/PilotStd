// web/src/views/__tests__/HomeView.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import HomeView from '@/views/HomeView.vue'
import http from '@/api/http'
import zhCN from '@/locales/zh-CN.json'

vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn() } }))
vi.mock('@/stores/app', () => ({ useAppStore: () => ({ loggedIn: true }) }))

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
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始化：解析后端 JSON 字符串布局并渲染卡片', async () => {
    const mockLayout = [{ i: 'stats', x: 0, y: 0, w: 4, h: 6 }]
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: JSON.stringify(mockLayout) } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(http.get).toHaveBeenCalledWith('/user/layout')
    expect(wrapper.vm.layout.length).toBe(1)
    expect(wrapper.vm.layout[0].i).toBe('stats')
  })

  it('初始化：后端返回空数组时加载默认 5 张卡片', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: '[]' } })

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(wrapper.vm.layout.length).toBe(5)
  })

  it('初始化：后端返回 null 时降级到默认布局', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: null } })

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
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: '[]' } })
    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    expect(wrapper.vm.isLocked).toBe(true)
    const grid = wrapper.findComponent({ name: 'GridLayout' })
    expect(grid.props('isDraggable')).toBe(false)
    expect(grid.props('isResizable')).toBe(false)
  })

  it('解锁：isLocked=false 后 GridLayout 可拖拽可缩放', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: '[]' } })
    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    wrapper.vm.isLocked = false
    await wrapper.vm.$nextTick()
    const grid = wrapper.findComponent({ name: 'GridLayout' })
    expect(grid.props('isDraggable')).toBe(true)
    expect(grid.props('isResizable')).toBe(true)
  })

  it('持久化：layout-updated 后防抖 500ms 才发 PUT', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: '[]' } })
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
    expect(url).toBe('/user/layout')
    // body 不含 component 实例
    const parsed = JSON.parse(body.layout)
    expect(parsed[0]).not.toHaveProperty('component')
    expect(parsed[0]).toHaveProperty('i')
    expect(parsed[0]).toHaveProperty('x')
  })

  it('Payload：PUT 格式严格为 {layout: JSON.stringify([...])}', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { layout: '[]' } })
    vi.mocked(http.put).mockResolvedValueOnce({})

    const wrapper = mountHome()
    await vi.runAllTimersAsync()

    const testLayout = wrapper.vm.layout.map((l: any) => ({ i: l.i, x: 0, y: 0, w: l.w, h: l.h }))
    const grid = wrapper.findComponent({ name: 'GridLayout' })
    grid.vm.$emit('update:layout', testLayout)
    await vi.advanceTimersByTimeAsync(500)

    const body = (vi.mocked(http.put).mock.calls[0] as any)[1]
    expect(body).toHaveProperty('layout')
    expect(() => JSON.parse(body.layout)).not.toThrow()
  })
})
