// web/src/composables/useNotificationLogs.test.ts — 通知日志页 composable 单元测试
//
// NEW-44 补齐：此前 `useNotificationLogs.ts` 无任何测试。只测 `useNotificationLogs()`
// 返回的 ref 与方法（对外行为），不测内部私有函数；用 mock 替身，不联网。
//   · 初始状态 + 挂载自动加载（列表 / 渠道元数据 / 上次筛选）
//   · 成功路径：数据写入 ref、分页/筛选参数序列化、页码与高度持久化
//   · 失败路径：错误可见（后端 error 优先 → i18n 兜底）、旧数据不清空、loading 收敛
//   · 边界：空列表、分页窗口（首/中/尾/总数不整除）、失败明细空响应
//   · 失败明细按需加载（未打开详情不发请求）与失败可见化
//   · 清理日志成功/失败（后端 error 与 i18n 兜底两条分支）
//   · 展示层映射、高亮行、拖拽调高与卸载清理
//
// 说明：源码**没有轮询**（onMounted 一次性加载 + 手动 loadLogs），也**没有已读标记**
// （诊断页刻意不提供"已读/未读"语义，见源码注释），故本文件不虚构这两类用例。
// useRoute/useI18n 用替身；生命周期通过 mount 一个 render-only 组件触发，不挂载 PrimeVue。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import type { ChannelSpec, FailedItem, NotificationLog } from '@/api/notification'

// ── 依赖替身（vi.hoisted：模块 mock 工厂先于 import 执行）──────────────
const mocks = vi.hoisted(() => ({
  getNotificationLogs: vi.fn(),
  deleteNotificationLogs: vi.fn(),
  getNotificationChannels: vi.fn(),
  getNotificationFailedItems: vi.fn(),
  t: vi.fn(),
  te: vi.fn(),
  route: null as unknown as { query: Record<string, unknown> },
}))

vi.mock('@/api/notification', () => ({
  getNotificationLogs: mocks.getNotificationLogs,
  deleteNotificationLogs: mocks.deleteNotificationLogs,
  getNotificationChannels: mocks.getNotificationChannels,
  getNotificationFailedItems: mocks.getNotificationFailedItems,
}))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: mocks.t, te: mocks.te }) }))

import { useNotificationLogs } from './useNotificationLogs'

// i18n 替身字典：te 只认这里声明的键（用于验证"未知键回退"分支）
const I18N: Record<string, string> = {
  'notification.logs.status.all': '全部',
  'notification.logs.status.success': '成功',
  'notification.logs.status.failed': '失败',
  'notification.logs.load_failed': '加载日志失败',
  'notification.logs.cleanup_result': '已清理 {n} 条记录',
  'notification.logs.cleanup_failed': '清理失败',
  'notification.config.error_type.timeout': '超时',
  'notification.config.error_type.unknown': '未知错误',
  'notification.channel.none': '无渠道',
  'notification.channel.wechat': '微信',
  'notification.event.archive_complete': '归档完成',
}

// ── 夹具与挂载入口（refs 原样留在 api，避免经 wrapper.vm 代理解包）─────
function log(id: number, overrides: Partial<NotificationLog> = {}): NotificationLog {
  return { id, event_type: 'archive_complete', channel: 'wechat', title: `通知 ${id}`, status: 'success', sent_at: '2026-01-01T10:00:00', is_read: false, failed_count: 0, ...overrides } as NotificationLog
}
const spec = (name: string, labelKey: string) => ({ name, label_key: labelKey } as ChannelSpec)
const failed = (n: string): FailedItem => ({ standard_number: n, standard_name: `标准 ${n}`, error_type: 'timeout', error_message: '超时' })

let api: ReturnType<typeof useNotificationLogs>
let wrapper: ReturnType<typeof mount> | undefined

function mountLogs() {
  wrapper = mount(defineComponent({ setup: () => (api = useNotificationLogs()), render: () => h('div') }))
}

describe('useNotificationLogs', () => {
  beforeEach(() => {
    localStorage.clear()
    mocks.route = reactive({ query: {} })
    mocks.t.mockReset().mockImplementation((key: string, params?: Record<string, unknown>) => {
      const raw = I18N[key] ?? key
      return params ? raw.replace(/\{(\w+)\}/g, (_m, name: string) => String(params[name] ?? '')) : raw
    })
    mocks.te.mockReset().mockImplementation((key: string) => key in I18N)
    mocks.getNotificationLogs.mockReset().mockResolvedValue({ total: 2, page: 1, page_size: 20, items: [log(1), log(2)] })
    mocks.getNotificationChannels.mockReset().mockResolvedValue({ channels: [spec('wechat', 'notification.channel.wechat'), spec('dingtalk', 'notification.channel.dingtalk')] })
    mocks.getNotificationFailedItems.mockReset()
    mocks.deleteNotificationLogs.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.restoreAllMocks()
  })

  it('初始状态：各状态为默认值，挂载即进入 loading', async () => {
    mocks.getNotificationLogs.mockReturnValue(new Promise(() => {}))
    mocks.getNotificationChannels.mockReturnValue(new Promise(() => {}))
    mountLogs()
    await nextTick()

    expect([api.loading.value, api.errMsg.value, api.page.value, api.pageSize, api.tableHeight.value]).toEqual([true, '', 1, 20, 400])
    expect([api.logs.value, api.total.value]).toEqual([[], 0])
    expect([api.filterChannel.value, api.filterStatus.value, api.filterStartDate.value, api.filterEndDate.value, api.highlightId.value]).toEqual([null, null, null, null, null])
    expect([api.detailVisible.value, api.detailItem.value]).toEqual([false, null])
    expect([api.failedItems.value, api.failedTotal.value, api.failedPage.value, api.failedPageSize, api.failedLoaded.value, api.failedError.value]).toEqual([[], 0, 1, 20, false, false])
    expect([api.cleanupVisible.value, api.cleanupDays.value, api.cleanupLoading.value, api.cleanupResult.value]).toEqual([false, 30, false, ''])
    expect(api.channelSpecs.value).toEqual([])
    expect(api.channelOptions.value).toEqual([{ label: '全部', value: null }])
    expect(api.statusOptions.value).toHaveLength(3)
  })

  it('挂载后按默认分页拉取日志并写入 ref；空响应正常清空', async () => {
    mountLogs()
    await flushPromises()

    expect(mocks.getNotificationLogs).toHaveBeenCalledWith({ page: 1, page_size: 20, channel: undefined, status: undefined, start_date: undefined, end_date: undefined }, '/notification-logs')
    expect(api.logs.value.map((l) => l.id)).toEqual([1, 2])
    expect([api.total.value, api.loading.value, api.errMsg.value]).toEqual([2, false, ''])

    mocks.getNotificationLogs.mockResolvedValueOnce({ total: 0, page: 1, page_size: 20, items: [] })
    await api.loadLogs()
    expect([api.logs.value, api.total.value]).toEqual([[], 0])
  })

  it('渠道元数据派生 channelOptions/statusOptions（未知 label_key 回退 name）', async () => {
    mountLogs()
    await flushPromises()

    expect(mocks.getNotificationChannels).toHaveBeenCalledTimes(1)
    expect(api.channelSpecs.value.map((s) => s.name)).toEqual(['wechat', 'dingtalk'])
    expect(api.channelOptions.value).toEqual([{ label: '全部', value: null }, { label: '微信', value: 'wechat' }, { label: 'dingtalk', value: 'dingtalk' }])
    expect(api.statusOptions.value).toEqual([{ label: '全部', value: null }, { label: '成功', value: 'success' }, { label: '失败', value: 'failed' }])
  })

  it('渠道元数据失败不阻断日志列表（下拉仅"全部"）', async () => {
    mocks.getNotificationChannels.mockRejectedValue(new Error('spec unavailable'))
    mountLogs()
    await flushPromises()

    expect(api.channelOptions.value).toEqual([{ label: '全部', value: null }])
    expect(api.logs.value).toHaveLength(2)
    expect(api.errMsg.value).toBe('')
  })

  it('从 storage 恢复页码/高度/筛选并按恢复页码请求，筛选变化后回写', async () => {
    const start = new Date(2026, 0, 2, 12) // 本地时间构造 ⇒ 断言与运行时时区无关
    const end = new Date(2026, 1, 3, 12)
    localStorage.setItem('pilotstd_notiflog_page', '3')
    localStorage.setItem('pilotstd_notiflog_height', '520')
    localStorage.setItem('pilotstd_notiflog_filters', JSON.stringify({ ch: 'wechat', st: 'failed', sd: start.toISOString(), ed: end.toISOString() }))
    mountLogs()
    await flushPromises()

    expect([api.page.value, api.tableHeight.value, api.filterChannel.value, api.filterStatus.value]).toEqual([3, 520, 'wechat', 'failed'])
    expect(api.filterStartDate.value).toBeInstanceOf(Date)
    expect(mocks.getNotificationLogs.mock.calls[0][0]).toMatchObject({ page: 3, channel: 'wechat', status: 'failed', start_date: '2026-01-02', end_date: '2026-02-03' })

    api.filterChannel.value = 'telegram'
    await nextTick()
    expect(JSON.parse(localStorage.getItem('pilotstd_notiflog_filters')!)).toEqual({ ch: 'telegram', st: 'failed', sd: start.toISOString(), ed: end.toISOString() })
  })

  it('loadLogs 序列化筛选/日期，请求期间置 loading', async () => {
    mountLogs()
    await flushPromises()
    mocks.getNotificationLogs.mockClear()
    mocks.getNotificationLogs.mockResolvedValue({ total: 1, page: 1, page_size: 20, items: [log(9)] })
    api.filterChannel.value = 'wechat'; api.filterStatus.value = 'failed'
    api.filterStartDate.value = new Date(2026, 0, 2, 12); api.filterEndDate.value = new Date(2026, 1, 3, 12)

    const pending = api.loadLogs()
    expect(api.loading.value).toBe(true)
    await pending

    expect(mocks.getNotificationLogs).toHaveBeenCalledWith({ page: 1, page_size: 20, channel: 'wechat', status: 'failed', start_date: '2026-01-02', end_date: '2026-02-03' }, '/notification-logs')
    expect([api.logs.value.map((l) => l.id), api.total.value, api.loading.value]).toEqual([[9], 1, false])
  })

  it('loadLogs 失败：后端 error 优先、无则 i18n 兜底；旧数据保留、loading 收敛', async () => {
    mountLogs()
    await flushPromises()

    mocks.getNotificationLogs.mockRejectedValueOnce({ response: { data: { error: '后端返回的错误' } } })
    await api.loadLogs()
    expect([api.errMsg.value, api.loading.value, api.logs.value.length]).toEqual(['后端返回的错误', false, 2])

    mocks.getNotificationLogs.mockRejectedValueOnce(new Error('network down'))
    await api.loadLogs()
    expect([api.errMsg.value, api.loading.value]).toEqual(['加载日志失败', false])
  })

  it('onPageChange 持久化页码；onSearch 回第 1 页；onReset 清空筛选', async () => {
    mountLogs()
    await flushPromises()

    mocks.getNotificationLogs.mockClear()
    api.onPageChange(3)
    await flushPromises()
    expect([api.page.value, localStorage.getItem('pilotstd_notiflog_page'), mocks.getNotificationLogs.mock.calls.at(-1)?.[0].page]).toEqual([3, '3', 3])

    mocks.getNotificationLogs.mockClear()
    api.onSearch()
    await flushPromises()
    expect([api.page.value, mocks.getNotificationLogs.mock.calls.at(-1)?.[0].page]).toEqual([1, 1])

    api.filterChannel.value = 'wechat'; api.filterStatus.value = 'failed'
    api.filterStartDate.value = new Date(2026, 0, 2, 12); api.filterEndDate.value = new Date(2026, 1, 3, 12); api.page.value = 5
    mocks.getNotificationLogs.mockClear()
    api.onReset()
    await flushPromises()
    expect([api.filterChannel.value, api.filterStatus.value, api.filterStartDate.value, api.filterEndDate.value, api.page.value]).toEqual([null, null, null, null, 1])
    expect(mocks.getNotificationLogs.mock.calls.at(-1)?.[0]).toMatchObject({ page: 1, channel: undefined, status: undefined, start_date: undefined, end_date: undefined })
  })

  it('未选中日志（detailItem 为空）时不请求失败明细', async () => {
    mountLogs()
    await flushPromises()

    await api.loadFailedItems()
    expect(mocks.getNotificationFailedItems).not.toHaveBeenCalled()
    expect(api.failedLoaded.value).toBe(false)
  })

  it('失败明细按需加载：成功写入并标记已加载；响应缺字段时回落', async () => {
    mountLogs()
    await flushPromises()
    api.detailItem.value = log(42, { failed_count: 3 })
    mocks.getNotificationFailedItems.mockResolvedValueOnce({ total: 3, page: 2, page_size: 20, items: [failed('GB/T 1-2026')] })

    await api.loadFailedItems(2)
    expect(mocks.getNotificationFailedItems).toHaveBeenCalledWith(42, 2, 20)
    expect([api.failedItems.value.map((i) => i.standard_number), api.failedTotal.value, api.failedPage.value, api.failedLoaded.value, api.failedError.value]).toEqual([['GB/T 1-2026'], 3, 2, true, false])

    mocks.getNotificationFailedItems.mockResolvedValueOnce({})
    await api.loadFailedItems(3)
    expect([api.failedItems.value, api.failedTotal.value, api.failedPage.value, api.failedLoaded.value]).toEqual([[], 0, 3, true])
  })

  it('失败明细加载失败：错误可见、保留旧明细、不抛异常', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mountLogs()
    await flushPromises()
    api.detailItem.value = log(42)
    mocks.getNotificationFailedItems.mockResolvedValueOnce({ total: 1, page: 1, page_size: 20, items: [failed('GB/T 1-2026')] })
    await api.loadFailedItems()

    const boom = new Error('failed-items down')
    mocks.getNotificationFailedItems.mockRejectedValueOnce(boom)
    await expect(api.loadFailedItems()).resolves.toBeUndefined()
    expect([api.failedError.value, api.failedLoaded.value, api.failedItems.value.length]).toEqual([true, false, 1])
    expect(warn).toHaveBeenCalledWith('[notification] failed-items load failed', boom)
  })

  it('doCleanup 成功：按天数清理、展示条数、关闭弹窗并刷新列表', async () => {
    mountLogs()
    await flushPromises()
    api.cleanupDays.value = 7
    api.cleanupVisible.value = true
    mocks.deleteNotificationLogs.mockResolvedValue({ ok: true, deleted: 5 })
    mocks.getNotificationLogs.mockClear()

    await api.doCleanup()
    expect(mocks.deleteNotificationLogs).toHaveBeenCalledWith(7)
    expect([api.cleanupResult.value, api.cleanupVisible.value, api.cleanupLoading.value]).toEqual(['已清理 5 条记录', false, false])
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1)
  })

  it('doCleanup 失败：后端 error 优先、无则 i18n 兜底，弹窗保持打开', async () => {
    mountLogs()
    await flushPromises()
    api.cleanupVisible.value = true

    mocks.deleteNotificationLogs.mockRejectedValueOnce({ response: { data: { error: '权限不足' } } })
    await api.doCleanup()
    expect([api.cleanupResult.value, api.cleanupVisible.value, api.cleanupLoading.value]).toEqual(['权限不足', true, false])

    mocks.deleteNotificationLogs.mockRejectedValueOnce(new Error('network down'))
    await api.doCleanup()
    expect([api.cleanupResult.value, api.cleanupLoading.value]).toEqual(['清理失败', false])
  })

  it('statusSeverity/statusLabel 与 errorTypeLabel 映射（未知错误类型回退 unknown 文案）', async () => {
    mountLogs()
    await flushPromises()

    expect([api.statusSeverity('success'), api.statusSeverity('failed'), api.statusSeverity('x')]).toEqual(['success', 'danger', 'info'])
    expect([api.statusLabel('success'), api.statusLabel('failed')]).toEqual(['成功', '失败'])
    expect([api.errorTypeLabel('timeout'), api.errorTypeLabel('made_up')]).toEqual(['超时', '未知错误'])
  })

  it('eventLabel 未知事件原样回显；channelLabel 已知翻译/none/未知原样', async () => {
    mountLogs()
    await flushPromises()

    expect([api.eventLabel('archive_complete'), api.eventLabel('brand_new_event')]).toEqual(['归档完成', 'brand_new_event'])
    expect([api.channelLabel('wechat'), api.channelLabel('none'), api.channelLabel('email')]).toEqual(['微信', '无渠道', 'email'])
  })

  it('totalPages/pages：空数据 1 页，窗口按当前页居中并收敛首尾', async () => {
    mountLogs()
    await flushPromises()

    api.total.value = 0; api.page.value = 1
    expect([api.totalPages(), api.pages()]).toEqual([1, [1]])

    api.total.value = 200 // 10 页
    expect([1, 5, 10].map((p) => { api.page.value = p; return api.pages() })).toEqual([[1, 2, 3, 4, 5], [3, 4, 5, 6, 7], [6, 7, 8, 9, 10]])

    api.total.value = 25; api.page.value = 2 // 不整除：2 页
    expect([api.totalPages(), api.pages()]).toEqual([2, [1, 2]])
  })

  it('showDetail 打开详情；rowClass 仅高亮 id 命中行', async () => {
    mountLogs()
    await flushPromises()
    const item = log(7)

    api.showDetail(item)
    expect([api.detailVisible.value, api.detailItem.value]).toEqual([true, item])
    api.highlightId.value = 7
    expect([api.rowClass(item), api.rowClass(log(8))]).toEqual(['highlight-row', ''])
  })

  it('URL highlight 参数写入 highlightId（深链定位）', async () => {
    mountLogs()
    await flushPromises()

    mocks.route.query = { highlight: '11' }
    await nextTick()
    expect(api.highlightId.value).toBe(11)
  })

  it('拖拽调高夹紧在 200~800，松手后写入 storage', async () => {
    mountLogs()
    await flushPromises()
    const preventDefault = vi.fn()

    api.onResizeStart({ preventDefault, clientY: 100 } as unknown as MouseEvent)
    expect(preventDefault).toHaveBeenCalledTimes(1)
    document.dispatchEvent(new MouseEvent('mousemove', { clientY: 600 })) // +500 ⇒ 超上限
    expect(api.tableHeight.value).toBe(800)
    document.dispatchEvent(new MouseEvent('mousemove', { clientY: -300 })) // -900 ⇒ 低于下限
    expect(api.tableHeight.value).toBe(200)
    document.dispatchEvent(new MouseEvent('mouseup'))
    expect(localStorage.getItem('pilotstd_notiflog_height')).toBe('200')
  })

  it('卸载时移除 document 拖拽监听（不再改变表格高度）', async () => {
    mountLogs()
    await flushPromises()
    api.onResizeStart({ preventDefault: vi.fn(), clientY: 100 } as unknown as MouseEvent)

    wrapper!.unmount()
    wrapper = undefined
    document.dispatchEvent(new MouseEvent('mousemove', { clientY: 600 }))
    expect(api.tableHeight.value).toBe(400)
  })
})
