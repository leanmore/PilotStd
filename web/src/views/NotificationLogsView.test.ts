import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationLogsView from './NotificationLogsView.vue'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

// mock notification API
const mockGetLogs = vi.fn().mockResolvedValue({
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
})
// P3：失败明细按需加载（默认空；个别用例覆盖）
const mockGetFailedItems = vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
vi.mock('@/api/notification', () => ({
  getNotificationLogs: (...args: any[]) => mockGetLogs(...args),
  getNotificationFailedItems: (...args: any[]) => mockGetFailedItems(...args),
  NotificationLog: {} as any,
}))

const routes = [{ path: '/notification-logs', component: NotificationLogsView }]

function mountComponent(locale: 'zh-CN' | 'en' = 'zh-CN') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  const router = createRouter({ history: createMemoryHistory(), routes })

  return shallowMount(NotificationLogsView, {
    global: {
      plugins: [pinia, i18n, router],
      stubs: {
        Button: { name: 'Button', template: '<button class="p-button"><slot /></button>', props: ['icon', 'label', 'size', 'severity', 'loading', 'text', 'disabled'] },
        Select: { name: 'Select', template: '<select class="p-select"><slot /></select>', props: ['modelValue', 'options', 'optionLabel', 'optionValue'] },
        Calendar: { name: 'Calendar', template: '<div class="calendar" />', props: ['modelValue', 'locale', 'dateFormat', 'showIcon'] },
        Tag: { name: 'Tag', template: '<span class="tag">{{ value }}</span>', props: ['value', 'severity'] },
        Dialog: { name: 'Dialog', template: '<div class="dialog"><slot /></div>', props: ['visible', 'header', 'style', 'modal'] },
        Message: { name: 'Message', template: '<div class="message"><slot /></div>', props: ['severity', 'closable'] },
      },
    },
  })
}

describe('NotificationLogsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetLogs.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  })

  it('renders page title 通知日志', async () => {
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.page-title').text()).toBe('通知日志')
  })

  it('renders filter section with channel and status selects', () => {
    const wrapper = mountComponent()
    const selects = wrapper.findAll('.filter-item')
    // 渠道、状态、起始日期、结束日期 —— **不含**「已读」（见下方用例）
    expect(selects.length).toBe(4)
  })

  it('★ 不提供「已读/未读」筛选与显示（渠道无已读回传，本页是诊断工具）', () => {
    const wrapper = mountComponent()
    const html = wrapper.html()
    // 不出现「已读」「未读」文案（三语中该页的 read/unread 键已无消费方）
    expect(html).not.toContain('已读')
    expect(html).not.toContain('未读')
    // 筛选区不含该标签
    expect(html).not.toContain('notification.logs.field.is_read')
  })

  it('★ 表格不渲染「已读」列，且不渲染 API 不返回的 aggregated_count 徽标', async () => {
    mockGetLogs.mockResolvedValueOnce({
      items: [
        {
          id: 1, event_type: 'archive_complete', channel: 'wechat', title: '归档完成',
          body: 'ok', standard_number: null, status: 'success', error_msg: null,
          sent_at: '2026-06-30T10:00:00', is_read: false,
          // 后端**不返回** aggregated_count / link / icon（已核实）；即便传了也不应渲染
          aggregated_count: 5, link: 'https://example.invalid/x',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    await nextTick()
    const row = wrapper.find('tbody tr')
    // 表头列数：时间/渠道/事件/状态/标题/操作 = 6（原先 7，含「已读」）
    expect(wrapper.findAll('thead th').length).toBe(6)
    expect(row.text()).toContain('归档完成')
    expect(row.text()).not.toContain('×5')
    expect(row.find('a').exists()).toBe(false)
  })

  it('renders filter action buttons (查询 and 重置)', () => {
    const wrapper = mountComponent()
    const buttons = wrapper.findAll('.filter-actions')
    expect(buttons.length).toBe(1)
  })

  it('shows empty state when no logs returned', async () => {
    mockGetLogs.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.empty').exists()).toBe(true)
    expect(wrapper.find('.empty').text()).toBe('暂无通知记录')
  })

  it('renders log rows when API returns data', async () => {
    mockGetLogs.mockResolvedValueOnce({
      items: [
        { id: 1, event_type: 'archive_complete', channel: 'wechat', title: '归档完成', body: 'ok', standard_number: null, status: 'success', error_msg: null, sent_at: '2026-06-30T10:00:00', is_read: false },
        { id: 2, event_type: 'test', channel: 'telegram', title: '测试消息', body: 'hello', standard_number: null, status: 'failed', error_msg: 'timeout', sent_at: '2026-06-30T09:00:00', is_read: true },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    await nextTick()
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBe(2)
    expect(rows[0].text()).toContain('归档完成')
    expect(rows[1].text()).toContain('测试消息')
  })

  it('displays total record count', async () => {
    mockGetLogs.mockResolvedValueOnce({
      items: [{ id: 1, event_type: 'test', channel: 'wechat', title: 'T', body: 'B', standard_number: null, status: 'success', error_msg: null, sent_at: '2026-06-30T10:00:00', is_read: false }],
      total: 42,
      page: 1,
      page_size: 20,
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.table-meta').text()).toContain('共 42 条记录')
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', async () => {
    const zh = mountComponent('zh-CN')
    await nextTick()
    await nextTick()
    await nextTick()
    expect(zh.find('.page-title').text()).toBe('通知日志')
    expect(zh.find('.empty').text()).toBe('暂无通知记录')

    const english = mountComponent('en')
    await nextTick()
    await nextTick()
    await nextTick()
    expect(english.find('.page-title').text()).toBe('Notification Logs')
    expect(english.find('.empty').text()).toBe('No notification logs')
    expect(english.html()).toContain('Channel')
  })

  it('事件名与配置页统一（notification.event.*）：announcement_fetch_complete 显示「公告抓取完成」', async () => {
    mockGetLogs.mockResolvedValueOnce({
      items: [{ id: 1, event_type: 'announcement_fetch_complete', channel: 'wechat', title: 'T', body: 'B', standard_number: null, status: 'success', error_msg: null, sent_at: '2026-06-30T10:00:00', is_read: false }],
      total: 1,
      page: 1,
      page_size: 20,
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    await nextTick()
    // 统一前日志页显示短版本「公告抓取」，现与配置页一致用「公告抓取完成」
    expect(wrapper.find('tbody tr').text()).toContain('公告抓取完成')
    expect(wrapper.find('tbody tr').text()).not.toContain('公告抓取 ')
  })

  // ── P3：失败明细按需加载 + 技术枚举翻译 + 吞错可见化 ────────────────────────────

  it('失败明细**按需**加载（列表不拉明细），且技术枚举被翻译、未知取值不暴露原始码', async () => {
    mockGetLogs.mockResolvedValueOnce({
      items: [
        { id: 42, event_type: 'normalize_complete', channel: 'wechat', title: 'T', body: 'B', standard_number: null, status: 'failed', error_msg: null, sent_at: '2026-10-05T10:00:00', is_read: false, failed_count: 2 },
      ],
      total: 1, page: 1, page_size: 20,
    })
    mockGetFailedItems.mockResolvedValueOnce({
      items: [
        { standard_number: 'GB/T 1234-2020', standard_name: '甲', error_type: 'not_found', error_message: '源文件不存在' },
        // 未知技术码（如 SMTP_AUTH_FAILED）⇒ 必须回退 unknown 文案，绝不显示原始码
        { standard_number: 'GB 9-2020', standard_name: '-', error_type: 'SMTP_AUTH_FAILED', error_message: '…/file.pdf' },
      ],
      total: 2, page: 1, page_size: 20,
    })

    const wrapper = mountComponent()
    await nextTick(); await nextTick(); await nextTick()

    // 列表阶段**未**调用明细接口（按需）
    expect(mockGetFailedItems).not.toHaveBeenCalled()

    // 打开详情（Button 是 stub：label 在 props 上，故按 props 定位而不是文本）
    const buttons = wrapper.findAllComponents({ name: 'Button' })
    const viewBtn = buttons.find(b => String(b.props('label') ?? '').includes('查看'))
    expect(viewBtn).toBeTruthy()
    await viewBtn!.trigger('click')
    await nextTick()

    // 详情里出现"查看失败明细"入口 ⇒ 点击触发按需加载
    const detailBtn = wrapper
      .findAllComponents({ name: 'Button' })
      .find(b => String(b.props('label') ?? '').includes('查看失败明细'))
    expect(detailBtn).toBeTruthy()
    await detailBtn!.trigger('click')
    await nextTick(); await nextTick()

    expect(mockGetFailedItems).toHaveBeenCalledWith(42, 1, 20)
    const html = wrapper.html()
    expect(html).toContain('未找到')            // not_found 已翻译
    expect(html).not.toContain('not_found')     // 不暴露原始枚举
    expect(html).toContain('未知错误')          // 未知技术码回退
    expect(html).not.toContain('SMTP_AUTH_FAILED')
  })

  it('失败明细加载失败 ⇒ 明确提示（不静默显示"没有明细"）', async () => {
    mockGetLogs.mockResolvedValueOnce({
      items: [
        { id: 7, event_type: 'normalize_complete', channel: 'wechat', title: 'T', body: 'B', standard_number: null, status: 'failed', error_msg: null, sent_at: '2026-10-05T10:00:00', is_read: false, failed_count: 3 },
      ],
      total: 1, page: 1, page_size: 20,
    })
    mockGetFailedItems.mockRejectedValueOnce(new Error('api down'))
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    const wrapper = mountComponent()
    await nextTick(); await nextTick(); await nextTick()
    const viewBtn = wrapper
      .findAllComponents({ name: 'Button' })
      .find(b => String(b.props('label') ?? '').includes('查看'))
    await viewBtn!.trigger('click')
    await nextTick()
    const detailBtn = wrapper
      .findAllComponents({ name: 'Button' })
      .find(b => String(b.props('label') ?? '').includes('查看失败明细'))
    await detailBtn!.trigger('click')
    await nextTick(); await nextTick()

    expect(wrapper.html()).toContain('失败明细加载失败')
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
  })
})
