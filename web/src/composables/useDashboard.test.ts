// web/src/composables/useDashboard.test.ts — 仪表盘布局状态（模块级单例）单元测试
//
// NEW-44 补齐：此前 `useDashboard.ts` 无任何测试。本文件锁定对外契约：
//   · 模块级单例初始状态（layout 空 / isLocked=true / availableCards=全量注册表）
//   · 默认布局（5 卡、顺序、尺寸、组件与 titleKey）；resetLayout 深拷贝不受运行期修改影响
//   · availableCards 随 addCard/removeCard 动态取补集；未知 key 静默忽略
//   · 本地缓存（用户隔离 key）与服务器布局的优先级：server 有效才覆盖本地，否则保本地/默认
//   · 保存链路：本地先写、server 失败仅告警；payload 只保留 i/x/y/w/h
//   · 竞态：先发请求的过期响应被 fetchVersion 丢弃；500ms 防抖合并布局变更
// 依赖 stores 替身 + 真实 userStorage（localStorage）；9 个 .vue 卡片组件用轻量替身，不挂载 PrimeVue。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  app: { userId: 0 } as { userId: number },
  getDashboardLayout: vi.fn(),
  setDashboardLayout: vi.fn(),
}))

vi.mock('@/stores/app', () => ({ useAppStore: () => mocks.app }))
vi.mock('@/stores/preferences', () => ({
  usePreferencesStore: () => ({
    getDashboardLayout: mocks.getDashboardLayout,
    setDashboardLayout: mocks.setDashboardLayout,
  }),
}))
// 卡片组件只作为 COMPONENT_MAP 的占位身份，hydrateLayout 只判存在性（不挂载 PrimeVue）
vi.mock('@/components/dashboard/widgets/StatsCard.vue', () => ({ default: { name: 'StatsCard' } }))
vi.mock('@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue', () => ({ default: { name: 'A' } }))
vi.mock('@/components/dashboard/widgets/AdapterStatusQueryCard.vue', () => ({ default: { name: 'B' } }))
vi.mock('@/components/dashboard/widgets/RecentAnnounceCard.vue', () => ({ default: { name: 'C' } }))
vi.mock('@/components/dashboard/widgets/PendingItemsCard.vue', () => ({ default: { name: 'D' } }))
vi.mock('@/components/dashboard/widgets/SystemInfoCard.vue', () => ({ default: { name: 'E' } }))
vi.mock('@/components/dashboard/widgets/QuickActionsCard.vue', () => ({ default: { name: 'F' } }))
vi.mock('@/components/dashboard/widgets/TaskTrendCard.vue', () => ({ default: { name: 'G' } }))
vi.mock('@/components/dashboard/widgets/SystemLogCard.vue', () => ({ default: { name: 'H' } }))

import { useDashboard } from './useDashboard'

const DEFAULTS = ['stats', 'sysInfo', 'quickActions', 'announceAdapter', 'queryAdapter']
const cacheKey = (uid: number) => `user_${uid}_dashboard_layout`
const cachedLayout = (uid: number) => JSON.parse(localStorage.getItem(cacheKey(uid))!)

describe('useDashboard 模块级单例初始状态', () => {
  it('首次导入时 layout 为空、isLocked=true，availableCards 为全部 9 张卡', () => {
    const { layout, isLocked, availableCards } = useDashboard()

    expect(layout.value).toEqual([])
    expect(isLocked.value).toBe(true)
    expect(availableCards.value.map((c) => c.key)).toEqual([
      'stats', 'sysInfo', 'quickActions', 'announceAdapter', 'queryAdapter',
      'recentAnnounce', 'pending', 'trend', 'sysLog',
    ])
    expect(availableCards.value[0]).toEqual({ key: 'stats', labelKey: 'dashboard.card.stats' })
  })
})

describe('useDashboard', () => {
  let api: ReturnType<typeof useDashboard>

  beforeEach(() => {
    localStorage.clear()
    mocks.app.userId = 0
    mocks.getDashboardLayout.mockReset().mockResolvedValue(null)
    mocks.setDashboardLayout.mockReset().mockResolvedValue(true)
    api = useDashboard()
    api.resetLayout()
    api.isLocked.value = true
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('resetLayout 恢复 5 张默认卡（顺序/尺寸/组件/titleKey），深拷贝不受运行期修改影响', () => {
    expect(api.layout.value.map((c) => c.i)).toEqual(DEFAULTS)
    expect(api.layout.value.every((c) => c.component)).toBe(true)
    expect(api.layout.value[0]).toMatchObject({ i: 'stats', x: 0, y: 0, w: 4, h: 6 })
    expect(api.layout.value.find((c) => c.i === 'queryAdapter')).toMatchObject({
      w: 8, h: 10, titleKey: 'dashboard.card.queryAdapterTitle',
    })

    api.layout.value[0].w = 99
    api.resetLayout()
    expect(api.layout.value[0].w).toBe(4)
  })

  it('availableCards = 注册表 − 当前布局，随 addCard/removeCard 动态更新', () => {
    const keys = () => api.availableCards.value.map((c) => c.key)
    expect(keys()).toEqual(['recentAnnounce', 'pending', 'trend', 'sysLog'])

    api.addCard('pending')
    expect(keys()).not.toContain('pending')

    api.removeCard('stats')
    expect(keys()).toContain('stats')
  })

  it('addCard 按注册表尺寸追加新卡；未知 key 静默忽略', () => {
    const before = api.layout.value.length
    api.addCard('trend')

    expect(api.layout.value.at(-1)).toMatchObject({ i: 'trend', x: 0, y: 0, w: 4, h: 8 })
    expect(api.layout.value.at(-1).titleKey).toBeUndefined()

    api.addCard('not-a-card')
    expect(api.layout.value).toHaveLength(before + 1)
  })

  it('removeCard 只删除目标卡并保持其他卡顺序；未知 key 为 no-op', () => {
    api.removeCard('sysInfo')
    expect(api.layout.value.map((c) => c.i)).toEqual(['stats', 'quickActions', 'announceAdapter', 'queryAdapter'])

    api.removeCard('not-a-card')
    expect(api.layout.value).toHaveLength(4)
  })

  it('toggleLayoutLock：解锁不保存，重新锁定触发保存且 payload 仅 i/x/y/w/h', async () => {
    api.toggleLayoutLock()
    expect(api.isLocked.value).toBe(false)
    expect(mocks.setDashboardLayout).not.toHaveBeenCalled()

    api.toggleLayoutLock()
    expect(api.isLocked.value).toBe(true)
    await flushPromises()

    expect(mocks.setDashboardLayout).toHaveBeenCalledTimes(1)
    const payload = mocks.setDashboardLayout.mock.calls[0][0]
    expect(payload).toHaveLength(5)
    expect(payload[0]).toEqual({ i: 'stats', x: 0, y: 0, w: 4, h: 6 })
    expect('component' in payload[0]).toBe(false)
  })

  it('saveLayoutToServer：本地缓存先写（用户隔离 key），server 失败仅告警、不丢本地', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mocks.app.userId = 7
    mocks.setDashboardLayout.mockResolvedValueOnce(false)

    await api.saveLayoutToServer()

    expect(cachedLayout(7)).toHaveLength(5)
    expect(cachedLayout(7)[4]).toEqual({ i: 'queryAdapter', x: 6, y: 6, w: 8, h: 10 })
    expect(mocks.setDashboardLayout).toHaveBeenCalledTimes(1)
    expect(warn).toHaveBeenCalledWith('布局保存到服务器失败，已保留本地缓存')
  })

  it('未登录（userId=0）：saveLayoutToServer 不写用户隔离缓存，仍提交服务器', async () => {
    await api.saveLayoutToServer()

    expect(localStorage.length).toBe(0)
    expect(mocks.setDashboardLayout).toHaveBeenCalledTimes(1)
  })

  it('fetchLayout：服务器返回有效布局时覆盖并 hydrate（未登录不写本地缓存）', async () => {
    mocks.getDashboardLayout.mockResolvedValueOnce([{ i: 'trend', x: 1, y: 2, w: 4, h: 8 }])

    await api.fetchLayout()

    expect(mocks.getDashboardLayout).toHaveBeenCalledWith('/')
    expect(api.layout.value.map((c) => c.i)).toEqual(['trend'])
    expect(api.layout.value[0].component).toBeTruthy()
    expect(localStorage.length).toBe(0)
  })

  it('fetchLayout：服务器无数据时保留本地缓存布局（不回落默认）', async () => {
    mocks.app.userId = 7
    localStorage.setItem(cacheKey(7), JSON.stringify([{ i: 'pending', x: 0, y: 0, w: 6, h: 8 }]))
    mocks.getDashboardLayout.mockResolvedValueOnce([])

    await api.fetchLayout()

    expect(api.layout.value.map((c) => c.i)).toEqual(['pending'])
  })

  it('fetchLayout：服务器数据有效时回写用户隔离缓存（存原始布局而非 hydrate 对象）', async () => {
    mocks.app.userId = 7
    const raw = [{ i: 'sysLog', x: 0, y: 0, w: 8, h: 8 }]
    mocks.getDashboardLayout.mockResolvedValueOnce(raw)

    await api.fetchLayout()

    expect(cachedLayout(7)).toEqual(raw)
  })

  it('fetchLayout：本地缓存脏 JSON 时忽略并回落默认 5 卡布局', async () => {
    mocks.app.userId = 7
    localStorage.setItem(cacheKey(7), '{bad json')

    await api.fetchLayout()

    expect(api.layout.value.map((c) => c.i)).toEqual(DEFAULTS)
  })

  it('fetchLayout 竞态：后发请求先返回时，先发的过期响应被丢弃', async () => {
    const oldResponse = Promise.withResolvers<unknown>()
    mocks.getDashboardLayout.mockReturnValueOnce(oldResponse.promise)
    mocks.getDashboardLayout.mockResolvedValueOnce([{ i: 'trend', x: 0, y: 0, w: 4, h: 8 }])

    const oldCall = api.fetchLayout()
    await api.fetchLayout()
    expect(api.layout.value.map((c) => c.i)).toEqual(['trend'])

    oldResponse.resolve([{ i: 'stats', x: 0, y: 0, w: 4, h: 6 }])
    await oldCall
    expect(api.layout.value.map((c) => c.i)).toEqual(['trend'])
  })

  it('handleLayoutUpdated 500ms 防抖：窗口内多次变更只保存最后一次', async () => {
    vi.useFakeTimers()
    api.handleLayoutUpdated([{ i: 'stats', x: 0, y: 0, w: 4, h: 6 }])
    await vi.advanceTimersByTimeAsync(300)
    api.handleLayoutUpdated([{ i: 'sysLog', x: 0, y: 0, w: 8, h: 8 }])

    await vi.advanceTimersByTimeAsync(499)
    expect(mocks.setDashboardLayout).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(mocks.setDashboardLayout).toHaveBeenCalledTimes(1)
    expect(mocks.setDashboardLayout.mock.calls[0][0]).toEqual([{ i: 'sysLog', x: 0, y: 0, w: 8, h: 8 }])
  })

  it('hydrateLayout 丢弃注册表外的卡，并保留 titleKey 映射', () => {
    const result = api.hydrateLayout([
      { i: 'queryAdapter', x: 0, y: 0, w: 8, h: 10 },
      { i: 'ghost', x: 0, y: 0, w: 1, h: 1 },
    ])

    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ i: 'queryAdapter', titleKey: 'dashboard.card.queryAdapterTitle' })
    expect(result[0].component).toBeTruthy()
  })
})
