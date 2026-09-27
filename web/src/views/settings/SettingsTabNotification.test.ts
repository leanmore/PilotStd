// views/settings/SettingsTabNotification.test.ts — 通知设置 Tab 测试（文案已 i18n：notification.settings.*）
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import SettingsTabNotification from './SettingsTabNotification.vue'

function makeI18n(locale: 'zh-CN' | 'en') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
}

function mountTab(locale: 'zh-CN' | 'en' = 'zh-CN') {
  return mount(SettingsTabNotification, {
    global: {
      plugins: [makeI18n(locale)],
      stubs: {
        NotificationConfig: { name: 'NotificationConfig', template: '<div />', methods: { saveConfig: vi.fn() } },
        WechatTrustIP: true,
      },
    },
  })
}

describe('SettingsTabNotification', () => {
  it('渲染两个卡片标题', () => {
    const html = mountTab().html()
    expect(html).toContain('通知配置')
    expect(html).toContain('企业微信可信 IP 自动更新')
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', () => {
    const html = mountTab('en').html()
    expect(html).toContain('Notification Settings')
    expect(html).toContain('WeCom Trusted IP Auto Update')
    expect(html).not.toContain('通知配置')
  })

  it('暴露的 saveConfig 转发到 NotificationConfig 子组件', () => {
    const saveConfig = vi.fn()
    const wrapper = mount(SettingsTabNotification, {
      global: {
        plugins: [makeI18n('zh-CN')],
        stubs: {
          NotificationConfig: { name: 'NotificationConfig', template: '<div />', methods: { saveConfig } },
          WechatTrustIP: true,
        },
      },
    })
    ;(wrapper.vm as unknown as { saveConfig: () => void }).saveConfig()
    expect(saveConfig).toHaveBeenCalled()
  })
})
