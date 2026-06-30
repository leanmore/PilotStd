import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationLogsView from './NotificationLogsView.vue'
import zhCN from '@/locales/zh-CN.json'

// mock notification API
const mockGetLogs = vi.fn().mockResolvedValue({
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
})
vi.mock('@/api/notification', () => ({
  getNotificationLogs: (...args: any[]) => mockGetLogs(...args),
  NotificationLog: {} as any,
}))

const routes = [{ path: '/notification-logs', component: NotificationLogsView }]

function mountComponent() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
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
    expect(selects.length).toBe(5) // channel, status, read, start date, end date
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
})
