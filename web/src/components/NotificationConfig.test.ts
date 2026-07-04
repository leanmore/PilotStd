// components/NotificationConfig.test.ts — 通知配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import NotificationConfig from './NotificationConfig.vue'

// 使用 vi.hoisted 避免 mock 提升导致引用错误
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

vi.mock('@/composables/useNotificationAggregator', () => ({
  useNotificationAggregator: () => ({
    shouldShow: vi.fn(),
    getPauseState: () => ({ isPaused: false, remainingSeconds: 0 }),
    resume: vi.fn(),
  }),
}))

function mountConfig() {
  localStorage.clear()
  return mount(NotificationConfig, {
    global: {
      plugins: [PrimeVue],
      stubs: {
        Accordion: { template: '<div class="accordion-stub"><slot /></div>', props: ['multiple'] },
        AccordionTab: { template: '<div class="tab-stub"><slot name="header" /><slot /></div>', props: ['header'] },
        Password: { template: '<input class="password-stub" />', props: ['modelValue', 'placeholder', 'toggleMask', 'feedback', 'size'] },
        Select: { template: '<select class="select-stub"><slot /></select>', props: ['modelValue', 'options', 'optionLabel', 'optionValue', 'placeholder', 'multiple'] },
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

  it('渲染 Toast 页面内通知配置区', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('页面内通知')
    expect(wrapper.html()).toContain('启用弹出通知')
  })

  it('渲染智能聚合与暂停配置', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('智能聚合与暂停')
  })

  it('默认状态未暂停时不显示恢复横幅', async () => {
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).not.toContain('通知已暂停')
  })
})
