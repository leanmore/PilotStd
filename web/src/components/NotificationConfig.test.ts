// components/NotificationConfig.test.ts — 通知配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import NotificationConfig from './NotificationConfig.vue'

const { getNotificationConfigMock, putNotificationConfigMock, testNotificationMock } = vi.hoisted(() => ({
  getNotificationConfigMock: vi.fn(),
  putNotificationConfigMock: vi.fn(),
  testNotificationMock: vi.fn(),
}))

vi.mock('@/api/notification', () => ({
  getNotificationConfig: getNotificationConfigMock,
  putNotificationConfig: putNotificationConfigMock,
  testNotification: testNotificationMock,
}))

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
})
