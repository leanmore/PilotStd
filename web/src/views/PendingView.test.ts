// PendingView 测试（待确认标准重查）
//
// 契约：挂载 ensure() 加载查询站点；站点卡片选中态由 selectedSite 决定并持久化；
// adapters 的 loading/error 三态各有占位/错误/重试，且这两种状态下禁止重查；
// 「导入待确认清单」把服务端 pending_lookup 的标准号回填文本域；重查提交行列表 + 选中站点。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { getPendingItems, postRequery } from '@/api'
import PendingView from './PendingView.vue'

const storage = vi.hoisted(() => new Map<string, string>())
const adapters = vi.hoisted(() => ({
  list: [] as Array<{ name: string; display_name: string }>,
  loading: false,
  error: null as string | null,
  ensure: vi.fn(),
  refresh: vi.fn(),
}))
vi.mock('@/lib/storage', () => ({
  getItem: (k: string) => storage.get(k) ?? null,
  setItem: (k: string, v: string) => void storage.set(k, v),
  removeItem: (k: string) => void storage.delete(k),
}))
vi.mock('@/composables/useQueryAdapters', () => ({
  useQueryAdapters: () => ({
    adapters: adapters.list, loading: adapters.loading, error: adapters.error,
    ensure: adapters.ensure, refresh: adapters.refresh,
  }),
}))
vi.mock('@/api', () => ({ getPendingItems: vi.fn(), postRequery: vi.fn() }))

const SITES = [{ name: 'ahbz', display_name: '安徽标准' }, { name: 'gjb', display_name: '国军标' }]
const DataView = { name: 'DataView', props: ['value'], template: '<div class="dv"><slot name="list" :items="value" /></div>' }
const Paginator = { name: 'Paginator', props: ['first', 'rows', 'totalRecords'], emits: ['page'], template: '<div class="pg" />' }

function mountView() {
  return mount(PendingView, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { DataView, Paginator, LogBar: true },
    },
  })
}

function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('PendingView 待确认', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage.clear()
    adapters.list = JSON.parse(JSON.stringify(SITES))
    adapters.loading = false
    adapters.error = null
    vi.mocked(getPendingItems).mockResolvedValue({ items: [{ standard_number: 'GB/T 1' }, { standard_number: 'ISO 9001' }] } as never)
    vi.mocked(postRequery).mockResolvedValue({
      results: [{ standard_number: 'GB/T 1', standard_name: '标准一', status: '现行', status_key: 'active' }],
    } as never)
  })

  it('挂载调用 ensure 并渲染站点卡片；点击切换选中站点', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(adapters.ensure).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.site-card').length).toBe(2)
    expect(wrapper.text()).toContain('安徽标准')
    expect(wrapper.find('.site-card').classes()).toContain('active') // 默认 ahbz

    await wrapper.findAll('.site-card')[1].trigger('click')
    expect(wrapper.findAll('.site-card')[1].classes()).toContain('active')
    expect(wrapper.findAll('.site-card')[0].classes()).not.toContain('active')
    expect(storage.get('pending_site')).toBe('gjb')
  })

  it('站点加载中显示占位并禁用重查按钮', async () => {
    adapters.loading = true
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载站点列表…')
    expect(wrapper.findAll('.site-card').length).toBe(0)
    expect(button(wrapper, '重新查询')!.attributes('disabled')).toBeDefined()
  })

  it('站点加载失败显示错误与刷新按钮，点击刷新调用 refresh', async () => {
    adapters.error = '站点列表加载失败，请刷新重试'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('站点列表加载失败')

    await button(wrapper, '刷新')!.trigger('click')
    expect(adapters.refresh).toHaveBeenCalledTimes(1)
    expect(button(wrapper, '重新查询')!.attributes('disabled')).toBeDefined()
  })

  it('导入待确认清单：把标准号逐行回填并提示条数', async () => {
    const wrapper = mountView()
    await flushPromises()
    await button(wrapper, '导入待确认清单')!.trigger('click')
    await flushPromises()

    expect(getPendingItems).toHaveBeenCalledTimes(1)
    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('GB/T 1\nISO 9001')
    expect(wrapper.text()).toContain('已导入 2 条待确认标准')
  })

  it('重查提交 trim 后的标准号数组与选中站点，结果分页首行按恢复页码计算', async () => {
    storage.set('pending_page', '1')
    // 30 条结果：page=1、rows=25 ⇒ 首行索引 25，第二页从第 26 条开始
    const many = Array.from({ length: 30 }, (_, i) => ({
      standard_number: `GB/T ${i + 1}`, standard_name: `标准${i + 1}`, status: '现行', status_key: 'active',
    }))
    vi.mocked(postRequery).mockResolvedValue({ results: many } as never)

    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('textarea').setValue('  GB/T 1  \n\nISO 9001\n')
    await button(wrapper, '重新查询')!.trigger('click')
    await flushPromises()

    expect(postRequery).toHaveBeenCalledWith(['GB/T 1', 'ISO 9001'], 'ahbz')
    const pg = wrapper.findComponent({ name: 'Paginator' })
    expect(pg.props('first')).toBe(25) // page 1 * rows 25
    expect(wrapper.text()).toContain('GB/T 26')
    expect(wrapper.text()).not.toContain('GB/T 1\n')
  })

  it('重查失败显示「重新查询失败」且 loading 结束', async () => {
    vi.mocked(postRequery).mockRejectedValue(new Error('500'))
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('textarea').setValue('GB/T 1')
    await button(wrapper, '重新查询')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('重新查询失败')
    expect(button(wrapper, '重新查询')!.attributes('disabled')).toBeUndefined()
  })

  it('重查结果保留 _site 站点标签（2026-11-25 修复：原第二行 map 覆盖了它）', async () => {
    vi.mocked(postRequery).mockResolvedValue({
      results: [{ standard_number: 'GB/T 1-2020', standard_name: '标准1', status: '现行', status_key: 'active' }],
    } as never)

    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('textarea').setValue('GB/T 1-2020')
    await button(wrapper, '重新查询')!.trigger('click')
    await flushPromises()

    const vm = wrapper.vm as unknown as { results: Array<Record<string, unknown>> }
    expect(vm.results[0]._site).toBe('ahbz')
    // 站点标签渲染：Tag 取 _site 显示名，不再恒空
    expect(wrapper.text()).toContain('安徽标准')
  })
})
