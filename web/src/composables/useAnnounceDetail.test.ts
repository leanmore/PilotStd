// useAnnounceDetail：缓存命中/未命中、加载失败、解析状态派生 + XSS 清洗、行内编辑回滚、
// 批量确认编排、解析轮询（无附件拦截 + completed 收尾）——组件只消费 return 的状态/方法
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useAnnounceDetail } from './useAnnounceDetail'
import type { AnnouncementRecord } from '@/types/api'

const mocks = vi.hoisted(() => ({
  getDetail: vi.fn(), getRecords: vi.fn(), triggerParse: vi.fn(), getParseStatus: vi.fn(),
  updateRecord: vi.fn(), batchApprove: vi.fn(), cacheGet: vi.fn(), cacheSet: vi.fn(), cacheClear: vi.fn(),
  loadFavStatuses: vi.fn(), toggleFavorite: vi.fn(), reloadRecords: vi.fn(), loadAllRemaining: vi.fn(),
  notify: { success: vi.fn(), error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}))
vi.mock('@/api/announce', () => ({
  getAnnounceDetailLite: mocks.getDetail, getAnnounceRecords: mocks.getRecords, triggerParse: mocks.triggerParse,
  getParseStatus: mocks.getParseStatus, updateRecord: mocks.updateRecord, batchApprove: mocks.batchApprove,
}))
vi.mock('@/composables/useDetailCache', () => ({
  useDetailCache: () => ({ get: mocks.cacheGet, set: mocks.cacheSet, clear: mocks.cacheClear }),
}))
vi.mock('@/composables/useFavorite', async () => {
  const { ref: vueRef } = await import('vue')
  return { useFavorite: () => ({ favMap: vueRef({}), favStatusMap: vueRef({}), isFavLoading: vueRef(false), toggleFavorite: mocks.toggleFavorite, loadFavStatuses: mocks.loadFavStatuses }) }
})
vi.mock('@/composables/useIncrementalScroll', async () => {
  const { ref: vueRef, shallowRef } = await import('vue')
  return { useIncrementalScroll: () => ({ displayRecords: shallowRef([]), isLoadingMore: vueRef(false), showLoadAllButton: vueRef(false), loadAllRemaining: mocks.loadAllRemaining, totalCount: vueRef(0), reload: mocks.reloadRecords }) }
})
vi.mock('@/composables/useAppToast', () => ({ useAppToast: () => mocks.notify }))

const ANN = {
  id: 1, announce_no: 'A1', title: '公告', publish_date: '2026-01-01', source_url: '',
  attachment_url: 'http://f/a.pdf', site_name: '站', content: '<p>正文</p><script>alert(1)</script>',
  source: 'gb', source_type: 'gb', parse_status: 'pending',
}
function rec(id: number, over: Partial<AnnouncementRecord> = {}): AnnouncementRecord {
  return {
    id, announcement_id: 1, announce_no: 'A1', row_index: id, standard_number: `GB/T ${id}`, std_name: '旧名称',
    implement_date: null, expiry_date: null, superseded_by: null, status: 'draft', confidence: 0.9,
    raw_text: null, parser_engine: null, source_type: 'gb', created_at: '2026-01-01', updated_at: '2026-01-01', ...over,
  }
}
const DETAIL = { announcement: ANN, records: [rec(1)], parse_status: 'pending' as const }

async function mountDetail() {
  let api!: ReturnType<typeof useAnnounceDetail>
  mount(defineComponent({ setup() { api = useAnnounceDetail('A1', 'gb', ref(null)); return () => h('div') } }))
  await flushPromises()
  return api
}

describe('useAnnounceDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.cacheGet.mockReturnValue(null)
    mocks.getDetail.mockResolvedValue(DETAIL)
    mocks.loadFavStatuses.mockResolvedValue(undefined)
  })
  afterEach(() => { vi.useRealTimers() })

  it('缓存命中：用缓存建状态，不请求详情接口，仍加载收藏状态', async () => {
    mocks.cacheGet.mockReturnValue({ announcement: ANN, records: [rec(2)], parse_status: 'completed' })
    const api = await mountDetail()

    expect(mocks.getDetail).not.toHaveBeenCalled()
    expect(api.announcement.value?.announce_no).toBe('A1')
    expect(api.records.value).toHaveLength(1)
    expect(api.parseStatusLabelKey.value).toBe('announce.detail.parse_status.completed')
    expect([api.loading.value, mocks.loadFavStatuses.mock.calls.length]).toEqual([false, 1])
  })

  it('缓存未命中：拉详情并回写缓存（announcement/records/parse_status），loading 收敛', async () => {
    const api = await mountDetail()

    expect(mocks.getDetail).toHaveBeenCalledWith('A1', 'gb', '/announce')
    expect(api.announcement.value?.title).toBe('公告')
    expect(mocks.cacheSet).toHaveBeenCalledWith({ announcement: ANN, records: DETAIL.records, parse_status: 'pending' })
    expect(api.loading.value).toBe(false)
  })

  it('详情加载失败：弹 i18n 错误 toast，loading 收敛', async () => {
    mocks.getDetail.mockRejectedValueOnce(new Error('500'))
    const api = await mountDetail()

    expect(mocks.notify.error).toHaveBeenCalledWith({ summary: '加载失败', detail: '无法加载公告详情' })
    expect(api.loading.value).toBe(false)
  })

  it('解析状态派生 + sanitizedContent：label/severity/按钮文案/禁用条件，清洗 script 保留正文', async () => {
    const api = await mountDetail() // 详情：pending + 有附件

    expect([api.parseStatusLabelKey.value, api.parseStatusSeverity.value, api.parseButtonLabelKey.value]).toEqual(
      ['announce.detail.parse_status.pending', 'secondary', 'announce.detail.btn_parse'],
    )
    expect(api.parseButtonDisabled.value).toBe(false)
    expect(api.sanitizedContent.value).toContain('<p>正文</p>')
    expect(api.sanitizedContent.value).not.toContain('<script')

    // 缓存命中构造"已解析 + 无附件"：按钮变重新解析并禁用
    mocks.cacheGet.mockReturnValueOnce({ announcement: { ...ANN, attachment_url: '' }, records: [], parse_status: 'completed' })
    const done = await mountDetail()
    expect([
      done.parseStatusLabelKey.value, done.parseStatusSeverity.value,
      done.parseButtonLabelKey.value, done.parseButtonDisabled.value,
    ]).toEqual(['announce.detail.parse_status.completed', 'success', 'announce.detail.btn_reparse', true])
  })

  it('行内编辑：已确认锁定；草稿保存成功转待校对；失败回滚并提示', async () => {
    const api = await mountDetail()
    const approved = rec(1, { status: 'approved' })
    await api.onCellEditComplete({ data: approved, newValue: '新名称', field: 'std_name' })
    expect([approved.std_name, mocks.updateRecord.mock.calls.length]).toEqual(['旧名称', 0])
    expect(mocks.notify.warn).toHaveBeenCalledWith({ summary: '提示', detail: '已确认的记录不可编辑' })

    const draft = rec(2)
    mocks.updateRecord.mockResolvedValueOnce({})
    await api.onCellEditComplete({ data: draft, newValue: '新名称', field: 'std_name' })
    expect(mocks.updateRecord).toHaveBeenCalledWith(2, { std_name: '新名称' })
    expect([draft.std_name, draft.status]).toEqual(['新名称', 'pending_review'])

    const fail = rec(3)
    mocks.updateRecord.mockRejectedValueOnce(new Error('500'))
    await api.onCellEditComplete({ data: fail, newValue: '坏值', field: 'std_name' })
    expect(fail.std_name).toBe('旧名称')
    expect(mocks.notify.error).toHaveBeenCalledWith({ summary: '保存失败', detail: '请重试' })
  })

  it('批量确认：空选择不请求；成功清空并重载；errors 数组拼进错误明细', async () => {
    const api = await mountDetail()
    await api.handleBatchApprove()
    expect(mocks.batchApprove).not.toHaveBeenCalled()

    api.selectedRecords.value = [rec(1), rec(2)]
    mocks.batchApprove.mockResolvedValueOnce({ approved_count: 2 })
    await api.handleBatchApprove()
    expect(mocks.batchApprove).toHaveBeenCalledWith([1, 2])
    expect(mocks.notify.success).toHaveBeenCalledWith({ summary: '确认成功', detail: '已确认 2 条标准', life: 3000 })
    expect([api.selectedRecords.value.length, mocks.cacheClear.mock.calls.length, mocks.getDetail.mock.calls.length]).toEqual([0, 1, 2])

    api.selectedRecords.value = [rec(3)]
    mocks.batchApprove.mockRejectedValueOnce({ response: { data: { detail: { errors: ['记录已驳回', '缺少编号'] } } } })
    await api.handleBatchApprove()
    expect(mocks.notify.error).toHaveBeenCalledWith({ summary: '确认失败', detail: '记录已驳回；缺少编号', life: 5000 })
  })

  it('开始解析：无附件只提示不请求；有附件轮询到 completed 后清缓存、重载、提示条数', async () => {
    const api = await mountDetail()
    api.announcement.value = { ...ANN, attachment_url: '' }
    await api.startParse()
    expect([mocks.triggerParse.mock.calls.length, mocks.notify.warn.mock.calls.length]).toEqual([0, 1])

    vi.useFakeTimers()
    api.announcement.value = { ...ANN }
    mocks.triggerParse.mockResolvedValueOnce({})
    mocks.getParseStatus.mockResolvedValueOnce({ status: 'completed', record_count: 5 })
    // 解析完成后会再次拉详情（后端此时已回 completed）
    mocks.getDetail.mockResolvedValueOnce({ ...DETAIL, parse_status: 'completed' })
    const p = api.startParse()
    await flushPromises()
    expect([
      api.parsing.value, api.parseStatusLabelKey.value,
      api.parseButtonLabelKey.value, api.parseButtonDisabled.value,
    ]).toEqual([true, 'announce.detail.parse_status.parsing', 'announce.detail.btn_parsing', true])

    await vi.advanceTimersByTimeAsync(2000)
    await p
    await flushPromises()
    expect(mocks.getParseStatus).toHaveBeenCalledWith('A1', 'gb')
    expect([api.parsing.value, api.parseStatusLabelKey.value]).toEqual([false, 'announce.detail.parse_status.completed'])
    expect(mocks.cacheClear).toHaveBeenCalled()
    // 降级模式条数取本地 records（分页模式才用 record_count）
    expect(mocks.notify.success).toHaveBeenCalledWith({ summary: '解析完成', detail: '共 1 条标准', life: 3000 })
  })
})
