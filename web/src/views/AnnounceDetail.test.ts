// AnnounceDetail 测试（公告详情装配层）：取数/编排在 useAnnounceDetail 中，本文件锁定视图契约 ——
// 挂载取详情参数、缓存命中不请求、无附件隐藏解析按钮、解析轮询完成后的状态、
// 已确认记录不可编辑、批量确认的 id 载荷、加载失败提示。
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import {
  getAnnounceDetailLite, triggerParse, getParseStatus, updateRecord, batchApprove, getBatchFavoriteStatus,
} from '@/api/announce'
import AnnounceDetail from './AnnounceDetail.vue'

const notify = vi.hoisted(() => ({
  success: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn(), removeGroup: vi.fn(),
}))
vi.mock('@/composables/useAppToast', () => ({ useAppToast: () => notify }))
vi.mock('@/api/announce', () => ({
  getAnnounceDetailLite: vi.fn(), getAnnounceRecords: vi.fn(), triggerParse: vi.fn(),
  getParseStatus: vi.fn(), updateRecord: vi.fn(), batchApprove: vi.fn(),
  addFavorite: vi.fn(), getBatchFavoriteStatus: vi.fn(), removeFavorite: vi.fn(),
}))
const DETAIL = {
  announcement: {
    announce_no: 'A-1', title: '国家标准公告', source_url: 'http://src', site_name: '来源站',
    source_type: 'gb', attachment_url: 'http://x/a.pdf', content: '<p>正文</p>', publish_date: '2026-01-01',
  },
  records: [
    { id: 1, row_index: 1, standard_number: 'GB/T 1', std_name: '标准一', status: 'draft' },
    { id: 2, row_index: 2, standard_number: '', std_name: '', status: 'approved' },
  ],
  parse_status: 'pending',
}

// 滚动哨兵会创建 IntersectionObserver（test-setup 的箭头 mock 不可 new），换成可构造实现
const BaseIO = (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver
class IOStub { observe() {} unobserve() {} disconnect() {} }
beforeAll(() => { (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IOStub })
afterAll(() => { (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = BaseIO })
async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/announce/:source/:announceNo', component: AnnounceDetail },
      { path: '/announce', component: { template: '<div />' } },
    ],
  })
  await router.push('/announce/anc_gb/A-1')
  await router.isReady()
  const wrapper = mount(AnnounceDetail, {
    global: {
      plugins: [PrimeVue, router, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { AppTable: true, Column: true, TableLoadFooter: true, FavoriteStatusTag: true, AppCalendar: true },
    },
  })
  await flushPromises()
  return wrapper
}

function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}
describe('AnnounceDetail 公告详情', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    vi.mocked(getAnnounceDetailLite).mockResolvedValue(JSON.parse(JSON.stringify(DETAIL)) as never)
    vi.mocked(getBatchFavoriteStatus).mockResolvedValue({ statuses: {} } as never)
    vi.mocked(triggerParse).mockResolvedValue({ status: 'parsing' } as never)
    vi.mocked(updateRecord).mockResolvedValue({ status: 'ok' } as never)
    vi.mocked(batchApprove).mockResolvedValue({ approved_count: 2 } as never)
  })
  afterEach(() => vi.restoreAllMocks())

  it('挂载按路由参数取详情并渲染公告头与记录数', async () => {
    const wrapper = await mountView()
    expect(getAnnounceDetailLite).toHaveBeenCalledWith('A-1', 'anc_gb', '/announce')
    expect(wrapper.text()).toContain('A-1')
    expect(wrapper.text()).toContain('国家标准公告')
    expect(wrapper.text()).toContain('标准清单（2 条）')
    expect(wrapper.find('.announce-detail__loading').exists()).toBe(false)
  })

  it('sessionStorage 详情缓存命中时不重复请求接口', async () => {
    sessionStorage.setItem('detail_anc_gb_A-1', JSON.stringify({ ...DETAIL, parse_status: 'completed', _ts: Date.now() }))
    const wrapper = await mountView()
    expect(getAnnounceDetailLite).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('已解析')
  })

  it('公告无附件时不显示解析按钮', async () => {
    const noAttach = JSON.parse(JSON.stringify(DETAIL))
    noAttach.announcement.attachment_url = ''
    vi.mocked(getAnnounceDetailLite).mockResolvedValue(noAttach as never)
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('无附件')
    expect(button(wrapper, '开始解析')).toBeFalsy()
  })

  it('解析轮询到 completed 后显示「已解析」并提示成功', async () => {
    let poll: (() => Promise<void>) | null = null
    vi.spyOn(globalThis, 'setInterval').mockImplementation(((cb: never) => { poll = cb; return 1 }) as never)
    vi.mocked(getParseStatus).mockResolvedValue({ status: 'completed', record_count: 2 } as never)
    const completed = JSON.parse(JSON.stringify(DETAIL))
    completed.parse_status = 'completed'

    const wrapper = await mountView()
    await button(wrapper, '开始解析')!.trigger('click')
    await flushPromises()
    expect(triggerParse).toHaveBeenCalledWith('A-1', 'anc_gb')

    vi.mocked(getAnnounceDetailLite).mockResolvedValue(completed as never)
    await poll!()
    await flushPromises()
    expect(getParseStatus).toHaveBeenCalledWith('A-1', 'anc_gb')
    expect(notify.success).toHaveBeenCalledWith(expect.objectContaining({ summary: '解析完成' }))
    expect(wrapper.text()).toContain('已解析')
  })

  it('已确认（approved）记录编辑被拒绝：不发 updateRecord 且值回滚', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      // eslint-disable-next-line no-unused-vars -- 参数名用于表达回调契约
      onCellEditComplete: (_e: { data: Record<string, unknown>; newValue: string; field: string }) => Promise<void>
    }
    const data = { id: 2, status: 'approved', standard_number: '旧号' }
    await vm.onCellEditComplete({ data, newValue: '新号', field: 'standard_number' })
    expect(updateRecord).not.toHaveBeenCalled()
    expect(data.standard_number).toBe('旧号')
    expect(notify.warn).toHaveBeenCalledWith(expect.objectContaining({ detail: '已确认的记录不可编辑' }))
  })

  it('批量确认把选中记录 id 原样提交并清空选择', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      selectedRecords: Array<{ id: number }>
      handleBatchApprove: () => Promise<void>
    }
    vm.selectedRecords = [{ id: 7 }, { id: 8 }]
    await vm.handleBatchApprove()
    await flushPromises()
    expect(batchApprove).toHaveBeenCalledWith([7, 8])
    expect(notify.success).toHaveBeenCalledWith(expect.objectContaining({ summary: '确认成功' }))
    expect(vm.selectedRecords).toEqual([])
  })

  it('详情接口失败时提示「加载失败」且结束 loading', async () => {
    vi.mocked(getAnnounceDetailLite).mockRejectedValue(new Error('boom'))
    const wrapper = await mountView()
    expect(notify.error).toHaveBeenCalledWith(expect.objectContaining({ summary: '加载失败' }))
    expect(wrapper.find('.announce-detail__loading').exists()).toBe(false)
  })
})
