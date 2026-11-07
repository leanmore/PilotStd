// components/NotificationBell.test.ts — 通知铃铛组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { computed, ref } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import NotificationBell from './NotificationBell.vue'

// 使用 Vue 的 ref/computed 让模板自动解包
const messages = ref([
  { id: 1, event_type: 'archive_complete', title: '归档完成', body: '文件已归档', is_read: false, sent_at: new Date().toISOString() },
  { id: 2, event_type: 'auto_scan_failed', title: '扫描异常', body: '连接超时', is_read: true, sent_at: new Date(Date.now() - 7200000).toISOString() },
])

const markAsReadMock = vi.fn().mockResolvedValue({ ok: true })
vi.mock('@/composables/useNotification', () => ({
  useNotification: () => ({
    messages,
    unreadCount: computed(() => messages.value.filter(m => !m.is_read).length),
    markAsRead: markAsReadMock,
  }),
}))

// Mock PrimeVue Popover（jsdom 不支持渲染层）
vi.mock('primevue/popover', () => ({
  default: {
    name: 'Popover',
    template: '<div class="popover-stub"><slot /></div>',
    props: ['appendTo', 'show'],
    methods: { toggle() {}, hide() {} },
  },
}))

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return { ...actual, useRouter: () => ({ push: mockPush }) }
})

function mountBell(locale: 'zh-CN' | 'en' = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notification-logs', component: { template: '<div>logs</div>' } },
      { path: '/', component: { template: '<div>home</div>' } },
    ],
  })
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  return mount(NotificationBell, {
    global: { plugins: [PrimeVue, router, i18n] },
  })
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    markAsReadMock.mockResolvedValue({ ok: true })
    messages.value = [
      { id: 1, event_type: 'archive_complete', title: '归档完成', body: '文件已归档', is_read: false, sent_at: new Date().toISOString() },
      { id: 2, event_type: 'auto_scan_failed', title: '扫描异常', body: '连接超时', is_read: true, sent_at: new Date(Date.now() - 7200000).toISOString() },
    ]
  })

  it('渲染铃铛按钮并显示 aria-label', () => {
    const wrapper = mountBell()
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('aria-label')).toBe('通知')
  })

  it('有未读消息时按钮 severity 为 primary', () => {
    const wrapper = mountBell()
    const btn = wrapper.find('button')
    expect(btn.attributes('data-p-severity')).toBe('primary')
  })

  it('无未读消息时按钮 severity 为 secondary', () => {
    messages.value[0].is_read = true
    const wrapper = mountBell()
    const btn = wrapper.find('button')
    expect(btn.attributes('data-p-severity')).toBe('secondary')
  })

  it('空消息列表时正常渲染不崩溃', () => {
    messages.value = []
    const wrapper = mountBell()
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('popover 内渲染通知列表项', () => {
    const wrapper = mountBell()
    expect(wrapper.html()).toContain('归档完成')
    expect(wrapper.html()).toContain('查看全部通知')
  })

  it('同一事件的多渠道副本只显示一条、角标只算一条，点击时全部标记已读', async () => {
    const sentAt = new Date().toISOString()
    messages.value = [
      { id: 11, event_type: 'archive_complete', channel: 'wechat', title: '归档完成', body: '同一事件', is_read: false, sent_at: sentAt },
      { id: 12, event_type: 'archive_complete', channel: 'telegram', title: '归档完成', body: '同一事件', is_read: false, sent_at: sentAt },
    ]
    const wrapper = mountBell()
    expect(wrapper.findAll('.notification-item')).toHaveLength(1)
    expect(wrapper.find('.p-badge').text()).toBe('1')

    await wrapper.find('.notification-item').trigger('click')
    await flushPromises()
    expect(markAsReadMock).toHaveBeenCalledTimes(2)
    expect(markAsReadMock).toHaveBeenCalledWith(11)
    expect(markAsReadMock).toHaveBeenCalledWith(12)
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', () => {
    const zh = mountBell('zh-CN')
    expect(zh.find('button').attributes('aria-label')).toBe('通知')
    expect(zh.html()).toContain('全部标记已读')

    const english = mountBell('en')
    expect(english.find('button').attributes('aria-label')).toBe('Notifications')
    expect(english.html()).toContain('Mark all as read')
    expect(english.html()).toContain('View all notifications')
  })
})
