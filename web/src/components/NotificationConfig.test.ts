// components/NotificationConfig.test.ts — 通知配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import NotificationConfig from './NotificationConfig.vue'

const { getNotificationConfigMock, putNotificationConfigMock, testNotificationMock, getNotificationChannelsMock } = vi.hoisted(() => ({
  getNotificationConfigMock: vi.fn(),
  putNotificationConfigMock: vi.fn(),
  testNotificationMock: vi.fn(),
  getNotificationChannelsMock: vi.fn(),
}))

vi.mock('@/api/notification', () => ({
  getNotificationConfig: getNotificationConfigMock,
  putNotificationConfig: putNotificationConfigMock,
  testNotification: testNotificationMock,
  getNotificationChannels: getNotificationChannelsMock,
}))
/** 渠道元数据夹具：形状与 `GET /api/notification/channels` 一致（字段取最小可用集） */
const CHANNEL_FIXTURE = {
  spec_hash: '0123456789abcdef',
  channels: [
    {
      name: 'wechat', label_key: 'notification.channel.wechat', icon: 'pi pi-comments',
      enabled_default: true, hint_key: '',
      fields: [{ name: 'webhook_url', type: 'string', label_key: '', label: 'Webhook URL', required: false, mask: true, password: false, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '' }],
      status_rule: { branches: [{ all_of: ['webhook_url'], label_key: 'notification.config.status.configured' }], fallback_key: 'notification.config.status.pending' },
    },
    {
      name: 'telegram', label_key: 'notification.channel.telegram', icon: 'pi pi-send',
      enabled_default: false, hint_key: '',
      fields: [{ name: 'bot_token', type: 'password', label_key: '', label: 'Bot Token', required: true, mask: true, password: true, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '' }],
      status_rule: { branches: [{ all_of: ['bot_token'], label_key: 'notification.config.status.configured' }], fallback_key: 'notification.config.status.pending' },
    },
    {
      name: 'feishu', label_key: 'notification.channel.feishu', icon: 'pi pi-book',
      enabled_default: false, hint_key: '',
      fields: [{ name: 'webhook_url', type: 'string', label_key: '', label: 'Webhook URL', required: true, mask: true, password: false, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '' }],
      status_rule: { branches: [{ all_of: ['webhook_url'], label_key: 'notification.config.status.configured' }], fallback_key: 'notification.config.status.pending' },
    },
    {
      name: 'dingtalk', label_key: 'notification.channel.dingtalk', icon: 'pi pi-bolt',
      enabled_default: false, hint_key: '',
      fields: [{ name: 'webhook_url', type: 'string', label_key: '', label: 'Webhook URL', required: true, mask: true, password: false, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '' }],
      status_rule: { branches: [{ all_of: ['webhook_url'], label_key: 'notification.config.status.configured' }], fallback_key: 'notification.config.status.pending' },
    },
  ],
}



function makeI18n(locale: 'zh-CN' | 'en' = 'zh-CN') {
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  return i18n
}

function mountConfig(locale: 'zh-CN' | 'en' = 'zh-CN') {
  localStorage.clear()
  return mount(NotificationConfig, {
    global: {
      plugins: [PrimeVue, makeI18n(locale)],
      stubs: {
        Password: { template: '<input class="password-stub" />', props: ['modelValue', 'placeholder', 'toggleMask', 'feedback', 'size'] },
        Calendar: true,
        AppCalendar: true,
      },
    },
  })
}

describe('NotificationConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    getNotificationChannelsMock.mockResolvedValue(CHANNEL_FIXTURE)
    getNotificationConfigMock.mockResolvedValue({
      enabled: true,
      channels: {
        wechat: { enabled: true, webhook_url: '', corpid: '', agentid: '', corpsecret: '', proxy_url: '' },
        telegram: { enabled: false, bot_token: '', chat_id: '' },
        feishu: { enabled: false, webhook_url: '', secret: '' },
        dingtalk: { enabled: false, webhook_url: '', secret: '' },
      },
      rules: {},
    })
  })

  it('渲染总开关', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('启用通知')
  })

  it('渲染四个渠道标签（企业微信/Telegram/飞书/钉钉）', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('企业微信')
    expect(html).toContain('Telegram')
    expect(html).toContain('飞书')
    expect(html).toContain('钉钉')
  })

  it('渲染静音时段配置区', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('静音时段')
    expect(wrapper.html()).toContain('启用静音时段')
  })

  it('渠道卡片使用 collapsible-card 而非 Accordion', () => {
    const wrapper = mountConfig()
    expect(wrapper.findComponent({ name: 'Accordion' }).exists()).toBe(false)
    expect(wrapper.find('.collapsible-card').exists()).toBe(true)
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', async () => {
    const zh = mountConfig('zh-CN')
    await new Promise(r => setTimeout(r, 10))
    await zh.vm.$nextTick()
    expect(zh.html()).toContain('启用通知')
    expect(zh.html()).toContain('企业微信')

    const english = mountConfig('en')
    await new Promise(r => setTimeout(r, 10))
    await english.vm.$nextTick()
    const html = english.html()
    expect(html).toContain('Enable Notifications')
    expect(html).toContain('WeCom')
    expect(html).toContain('Event subscriptions:')
    expect(html).not.toContain('启用通知')
    // 只断言「渲染出来的渠道标题」，模板注释里的中文（<!-- 企业微信 -->）不算文案
    expect(html).not.toContain('collapsible-title">企业微信')
  })

  it('事件名与日志页统一（notification.event.*）：announcement_fetch_complete 显示「公告抓取完成」', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    const html = wrapper.html()
    expect(html).toContain('公告抓取完成')
    expect(html).not.toContain('>公告抓取<')
  })
})
