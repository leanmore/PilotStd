// StandardsStatusView 分页模式：查询/刷新按钮必须重拉第一页（D-6 回归，2026-11-25）
//
// 背景：`VITE_USE_PAGINATED_RECORDS_API=true` 时 `loadList()` 首行直接 return（数据由
// useIncrementalScroll 按页拉取），原实现的「查询/刷新」都调 `loadList()` ⇒ 按钮完全无效。
// 修法：分页模式下这两个动作改走 `reloadRecords()`（用当前筛选重拉第一页）。
//
// 为什么用动态 import：`usePaginated` 在模块求值时读取 `import.meta.env`，
// 必须先 stubEnv 再求值模块，而静态 import 会被提升到 stubEnv 之前。
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { getStandardsStats, getStandardsStatus, clearStandardsStatusCache } from '@/api/standards'

const storage = vi.hoisted(() => new Map<string, string>())
vi.mock('@/lib/storage', () => ({
  getItem: (k: string) => storage.get(k) ?? null,
  setItem: (k: string, v: string) => void storage.set(k, v),
  removeItem: (k: string) => void storage.delete(k),
}))
vi.mock('@/api/standards', () => ({
  getStandardsStats: vi.fn(),
  getStandardsStatus: vi.fn(),
  clearStandardsStatusCache: vi.fn(),
}))

const ITEMS = [
  { id: 1, standard_number: 'GB/T 1', std_name: '标准一', status: '现行', status_key: 'active', last_checked_at: null, check_count: 0 },
]
const AppTable = {
  name: 'AppTable',
  props: ['value', 'loading'],
  template: '<div class="tbl"><div v-for="r in value" :key="r.id" class="rec">{{ r.standard_number }}</div></div>',
}

class IOStub { observe() {} unobserve() {} disconnect() {} }
const BaseIO = (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let View: any

beforeAll(async () => {
  ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IOStub
  vi.stubEnv('VITE_USE_PAGINATED_RECORDS_API', 'true')
  vi.resetModules()
  View = (await import('./StandardsStatusView.vue')).default
})

afterAll(() => {
  ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = BaseIO
  vi.unstubAllEnvs()
})

function mountView() {
  return mount(View, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { AppTable, Column: true },
    },
  })
}

function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('StandardsStatusView 分页模式（D-6 回归）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage.clear()
    vi.mocked(getStandardsStats).mockResolvedValue({ active: 1, inactive: 2, upcoming: 3, unknown: 0 } as never)
    vi.mocked(getStandardsStatus).mockResolvedValue({ total: 1, page: 1, page_size: 50, items: ITEMS } as never)
  })

  it('挂载时由增量滚动 fetcher 拉第一页（不走 loadList）', async () => {
    mountView()
    await flushPromises()
    expect(getStandardsStatus).toHaveBeenCalledTimes(1)
    const args = vi.mocked(getStandardsStatus).mock.calls[0][0] as { page: number }
    expect(args.page).toBe(1)
  })

  it('点击「查询」：分页模式下必须重拉（原实现直接 return → 按钮无效）', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(getStandardsStatus).toHaveBeenCalledTimes(1)

    await button(wrapper, '查询')!.trigger('click')
    await flushPromises()
    expect(getStandardsStatus).toHaveBeenCalledTimes(2)
  })

  it('点击「刷新」：先清缓存，再重拉（原实现只清缓存不重拉）', async () => {
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '刷新')!.trigger('click')
    await flushPromises()

    expect(clearStandardsStatusCache).toHaveBeenCalledTimes(1)
    expect(getStandardsStatus).toHaveBeenCalledTimes(2)
  })
})
