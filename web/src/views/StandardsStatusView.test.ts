// StandardsStatusView 测试（标准状态列表）
//
// 契约：挂载并行加载统计与列表；筛选条件持久化到 storage，变更时清缓存并重拉；
// 列表为空显示占位；接口错误优先取 FastAPI 422 的 detail[0].msg；总数/已显示文案随数据变化。
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { getStandardsStats, getStandardsStatus, clearStandardsStatusCache } from '@/api/standards'
import StandardsStatusView from './StandardsStatusView.vue'

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
  { id: 1, standard_number: 'GB/T 1', std_name: '标准一', status: '现行', status_key: 'active', last_checked_at: '2026-01-01T10:00:00', check_count: 3 },
  { id: 2, standard_number: 'GB/T 2', std_name: '', status: '废止', status_key: 'withdrawn', last_checked_at: null, check_count: 0 },
]
const AppTable = {
  name: 'AppTable',
  props: ['value', 'loading'],
  template: '<div class="tbl"><div v-for="r in value" :key="r.id" class="rec">{{ r.standard_number }}</div></div>',
}

// 视图里的滚动哨兵会创建 IntersectionObserver（test-setup 的箭头 mock 不可 new），
// 换成可构造的空实现，否则 watch 回调抛错会中断组件更新、DOM 断言全部失真。
const BaseIO = (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver
class IOStub { observe() {} unobserve() {} disconnect() {} }
beforeAll(() => {
  ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IOStub
})
afterAll(() => {
  ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = BaseIO
})

function mountView() {
  return mount(StandardsStatusView, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { AppTable, Column: true },
    },
  })
}

function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('StandardsStatusView 标准状态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage.clear()
    vi.mocked(getStandardsStats).mockResolvedValue({ active: 1, inactive: 2, unknown: 3 } as never)
    vi.mocked(getStandardsStatus).mockResolvedValue({ total: 120, page: 1, page_size: 100, items: ITEMS } as never)
  })

  it('挂载即加载统计与列表，请求参数固定从第 1 页 100 条开始', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getStandardsStats).toHaveBeenCalledWith('/standards-status')
    expect(getStandardsStatus).toHaveBeenCalledWith(
      { page: 1, page_size: 100, status: undefined, standard_no: undefined, name: undefined },
      '/standards-status',
    )
    const stats = wrapper.findAll('.stat-num').map((n) => n.text())
    expect(stats).toEqual(['1', '2', '3'])
  })

  it('渲染列表行、总数与「已显示 n / total」提示', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.rec').length).toBe(2)
    expect(wrapper.text()).toContain('共 120 条记录')
    expect(wrapper.text()).toContain('已显示 2 / 120 条')
  })

  it('空列表显示「暂无标准状态数据」', async () => {
    vi.mocked(getStandardsStatus).mockResolvedValue({ total: 0, page: 1, page_size: 100, items: [] } as never)
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无标准状态数据')
  })

  it('422 校验错误优先展示 detail[0].msg，而不是兜底文案', async () => {
    vi.mocked(getStandardsStatus).mockRejectedValue({ response: { data: { detail: [{ msg: '标准号格式不正确' }] } } })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('标准号格式不正确')
  })

  it('从 storage 恢复筛选条件：回填输入框且首次请求即带筛选参数', async () => {
    storage.set('standards_filters', JSON.stringify({ s: 'withdrawn', n: 'GB', m: '标准' }))
    const wrapper = mountView()
    await flushPromises()

    expect(getStandardsStatus).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'withdrawn', standard_no: 'GB', name: '标准' }),
      '/standards-status',
    )
    const values = wrapper.findAll('input').map((i) => (i.element as HTMLInputElement).value)
    expect(values).toContain('GB')
    expect(values).toContain('标准')
  })

  it('修改筛选条件会写回 storage、清缓存并重新加载', async () => {
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as unknown as { filterStatus: string | null; filterStandardNo: string }
    vm.filterStatus = 'active'
    vm.filterStandardNo = 'ISO'
    await flushPromises()

    expect(clearStandardsStatusCache).toHaveBeenCalled()
    expect(JSON.parse(storage.get('standards_filters')!)).toEqual({ s: 'active', n: 'ISO', m: '' })
    expect(getStandardsStatus).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'active', standard_no: 'ISO' }),
      '/standards-status',
    )
  })

  it('点击刷新先清缓存再拉第一页', async () => {
    const wrapper = mountView()
    await flushPromises()
    vi.mocked(clearStandardsStatusCache).mockClear()
    vi.mocked(getStandardsStatus).mockClear()
    await button(wrapper, '刷新')!.trigger('click')
    await flushPromises()

    expect(clearStandardsStatusCache).toHaveBeenCalledTimes(1)
    expect(getStandardsStatus).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }), '/standards-status')
  })
})
