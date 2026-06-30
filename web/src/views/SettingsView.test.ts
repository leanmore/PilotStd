import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import SettingsView from './SettingsView.vue'
import zhCN from '@/locales/zh-CN.json'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'

// mock API 模块 — SettingsView 导入的函数较多
vi.mock('@/api', () => ({
  getUsers: vi.fn().mockResolvedValue({ users: [] }),
  addUser: vi.fn().mockResolvedValue({ ok: true }),
  deleteUser: vi.fn().mockResolvedValue({ ok: true }),
  changePassword: vi.fn().mockResolvedValue({ ok: true }),
  getSettings: vi.fn().mockResolvedValue({}),
  putSettings: vi.fn().mockResolvedValue({ ok: true }),
  uploadFile: vi.fn().mockResolvedValue({ url: '/bg.jpg' }),
  getToken: vi.fn().mockResolvedValue({ token: 'pst_mock_token' }),
  refreshToken: vi.fn().mockResolvedValue({ token: 'pst_new_token' }),
}))

// mock http 模块（熔断配置等）
vi.mock('@/api/http', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 } }),
    put: vi.fn().mockResolvedValue({ data: { ok: true } }),
  },
}))

// stub 子组件 — SettingsView 有大量子组件
const StubNotificationConfig = { name: 'NotificationConfig', template: '<div class="notification-config" />', methods: { saveConfig: vi.fn() } }
const StubWechatTrustIP = { name: 'WechatTrustIP', template: '<div class="wechat-trust-ip" />' }
const StubCacheManager = { name: 'CacheManager', template: '<div class="cache-manager" />' }
const StubFileMonitor = { name: 'FileMonitor', template: '<div class="file-monitor" />' }
const StubTaskManager = { name: 'TaskManager', template: '<div class="task-manager" />' }
const StubValidityConfig = { name: 'ValidityConfig', template: '<div class="validity-config" />', methods: { doSave: vi.fn() } }

// 导入 store 以获取 THEMES
import { useAppStore } from '@/stores/app'

const routes = [{ path: '/settings', component: SettingsView }]

function mountComponent() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({ history: createMemoryHistory(), routes })

  return shallowMount(SettingsView, {
    global: {
      plugins: [pinia, i18n, router, ConfirmationService, ToastService],
      stubs: {
        Button: { name: 'Button', template: '<button class="p-button">{{ label }}</button>', props: ['label', 'icon', 'size', 'severity', 'loading', 'text'] },
        ConfirmDialog: { name: 'ConfirmDialog', template: '<div class="confirm-dialog" />' },
        Toast: { name: 'Toast', template: '<div class="toast" />' },
        DataView: { name: 'DataView', template: '<div class="dataview"><slot name="list" :items="value" /></div>', props: ['value', 'size'] },
        Dialog: { name: 'Dialog', template: '<div class="dialog"><slot /></div>', props: ['visible', 'header', 'modal', 'style'] },
        Tag: { name: 'Tag', template: '<span class="tag">{{ value }}</span>', props: ['value', 'severity'] },
        Select: { name: 'Select', template: '<select class="p-select" />', props: ['modelValue', 'options', 'optionLabel', 'optionValue'] },
        InputNumber: { name: 'InputNumber', template: '<input type="number" class="inputnumber" />', props: ['modelValue', 'min', 'showButtons'] },
        Message: { name: 'Message', template: '<div class="message"><slot /></div>', props: ['severity', 'closable'] },
        NotificationConfig: StubNotificationConfig,
        WechatTrustIP: StubWechatTrustIP,
        CacheManager: StubCacheManager,
        FileMonitor: StubFileMonitor,
        TaskManager: StubTaskManager,
        ValidityConfig: StubValidityConfig,
      },
    },
  })
}

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title 设置', async () => {
    const wrapper = mountComponent()
    await nextTick()
    expect(wrapper.find('h1').text()).toBe('设置')
  })

  it('renders tab bar with all expected tabs', () => {
    const wrapper = mountComponent()
    const tabs = wrapper.findAll('.tab-bar button')
    expect(tabs.length).toBe(13)
  })

  it('defaults active tab to storage', () => {
    const wrapper = mountComponent()
    const activeBtn = wrapper.find('.tab-bar button.active')
    expect(activeBtn.exists()).toBe(true)
    expect(activeBtn.text()).toBe('存储')
  })

  it('renders storage card with form inputs when storage tab active', () => {
    const wrapper = mountComponent()
    // 存储 tab 应可见
    expect(wrapper.find('.card').exists()).toBe(true)
  })

  it('renders footer action bar with 应用 and 确定 buttons', () => {
    const wrapper = mountComponent()
    const footer = wrapper.find('.settings-footer')
    expect(footer.exists()).toBe(true)
    const buttons = footer.findAll('.p-button')
    expect(buttons.length).toBeGreaterThanOrEqual(2)
  })

  it('shows version info in footer', () => {
    const wrapper = mountComponent()
    const footer = wrapper.find('.settings-footer')
    expect(footer.text()).toContain('PilotStd v')
  })
})
