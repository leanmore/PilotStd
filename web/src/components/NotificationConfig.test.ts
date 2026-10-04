// components/NotificationConfig.test.ts — 通知配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import NotificationConfig from './NotificationConfig.vue'

const { getNotificationConfigMock, putNotificationConfigMock, testNotificationMock, getNotificationChannelsMock, getNotificationSpecMock } = vi.hoisted(() => ({
  getNotificationConfigMock: vi.fn(),
  putNotificationConfigMock: vi.fn(),
  testNotificationMock: vi.fn(),
  getNotificationChannelsMock: vi.fn(),
  getNotificationSpecMock: vi.fn(),
}))

vi.mock('@/api/notification', () => ({
  getNotificationConfig: getNotificationConfigMock,
  putNotificationConfig: putNotificationConfigMock,
  testNotification: testNotificationMock,
  getNotificationChannels: getNotificationChannelsMock,
  getNotificationSpec: getNotificationSpecMock,
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

/**
 * 可订阅事件夹具：形状与 `GET /api/notification/spec` 一致。
 * 取**完整 35 条**（= 后端规格 `subscribable=True` 的集合）——既有用例会断言其中若干条的事件文案，
 * 故默认夹具必须与生产一致；"零硬编码"的判据由专门用例用**小集合**反向验证。
 */
const EVENT_SPEC_FIXTURE = {
  events: [
    'archive_complete', 'standard_status_changed', 'standard_first_registered',
    'announcement_fetch_complete', 'auto_backup', 'announcement_check_complete',
    'auto_scan_failed', 'batch_download_complete', 'validity_batch_report',
    'validity_round_summary', 'validity_standard_failed', 'validity_system_failed',
    'favorite_created', 'download_started', 'download_complete', 'download_failed',
    'archive_abandoned', 'archive_failed', 'normalize_complete', 'normalize_failed',
    'scan_complete', 'scan_empty', 'batch_query_summary', 'query_failed', 'query_empty',
    'expire_standard_moved', 'replacement_not_found', 'announcement_fetch_failed',
    'announce_fetch_summary', 'date_reminder', 'task_execution_failed', 'quota_exhausted',
    'trust_ip_update', 'image_update_available', 'worker_error',
  ],
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
    getNotificationSpecMock.mockResolvedValue(EVENT_SPEC_FIXTURE)
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

  it('事件选项由 API 返回集合渲染（D5：前端零硬编码）', async () => {
    // 只给 3 条：若组件仍硬编码，就会渲染出集合外的事件，本用例即红
    getNotificationSpecMock.mockResolvedValue({ events: ['archive_complete', 'scan_complete', 'trust_ip_update'] })
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    // 判据：渲染出的选项集合 == API 返回集合
    for (const ev of ['archive_complete', 'scan_complete', 'trust_ip_update']) {
      expect(html).toContain(`id="wechat-${ev}"`)
    }
    // 未在 API 集合中的事件不得出现（证明不是硬编码渲染）
    expect(html).not.toContain('id="wechat-validity_batch_report"')
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
