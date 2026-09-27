// views/settings/SettingsTabsI18n.test.ts — 批 2 i18n 守卫：设置页 14 个文件的可见文案
//
// 目的（与 SettingsTabSchedule.test.ts 的 i18n 守卫同款）：
//   ① 每个组件都用**真实 locale 文件**挂载，切到 en 后可见文案必须随之变化；
//   ② 空 messages 会让 t() 直接回显 key，因此"文案是否真的走 i18n"能被断言出来；
//   ③ themes.ts 是模块级常量，用 labelKey + 渲染期翻译，这里直接断言三语都能解析且非 key 回显。
// PrimeVue 组件全部 stub（仓库既有测试同款做法）：只保留文案，避免 PrimeVue 内部生命周期噪音。
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'primevue/confirmationservice'
import { THEMES } from '@/config/themes'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

vi.mock('@/api', () => ({
  getUsers: vi.fn().mockResolvedValue({ users: [] }),
  addUser: vi.fn().mockResolvedValue({ ok: true }),
  deleteUser: vi.fn().mockResolvedValue({ ok: true }),
  changePassword: vi.fn().mockResolvedValue({ ok: true }),
  getToken: vi.fn().mockResolvedValue({ token: 'tk' }),
  refreshToken: vi.fn().mockResolvedValue({ token: 'tk2' }),
}))

// /adapter/config 必须返回完整熔断配置：freeze_durations 缺失会让模板取下标失败（既有行为）
const mockHttpGet = vi.fn()
vi.mock('@/api/http', () => ({
  default: {
    get: (...a: unknown[]) => mockHttpGet(...a),
    put: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

const ADAPTER_CONFIG = { failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 }
const CACHE_STATS = { total_size_mb: 1, max_size_mb: 50, auto_cleanup: true, cleanup_ratio: 0.1, tables: {} }
const WECHAT_CONFIG = { enabled: false, interval_hours: 6, cookie_source: 'manual', update_mode: 'append', engine: 'auto', cookie_status: '' }
const WECHAT_STATUS = { current_ip: '', last_ip: '', ip_changed: false, cookie_valid: false, enabled: false, last_check_at: '' }

type Locale = 'zh-CN' | 'zh-TW' | 'en'

function makeI18n(locale: Locale = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

/** 只渲染文案的 PrimeVue stub（label/value/header 走 $attrs，插槽原样透出） */
const TEXT_STUBS = {
  Button: { template: '<button>{{ $attrs.label }}<slot /></button>', inheritAttrs: false },
  InputText: { template: '<input :placeholder="$attrs.placeholder" />', inheritAttrs: false },
  InputNumber: { template: '<input type="number" />' },
  Password: { template: '<input type="password" />' },
  ToggleSwitch: { template: '<input type="checkbox" />' },
  Tag: { template: '<span class="tag">{{ $attrs.value }}<slot /></span>', inheritAttrs: false },
  Message: { template: '<div class="msg"><slot /></div>' },
  Dialog: { template: '<div class="dlg">{{ $attrs.header }}<slot /></div>', inheritAttrs: false },
  DataView: { template: '<div class="dv"><slot name="list" :items="[]" /></div>' },
  Select: { template: '<div class="select" />' },
  SelectButton: { template: '<div />' },
  Dropdown: { template: '<div class="dropdown" />' },
  Textarea: { template: '<textarea :placeholder="$attrs.placeholder" />', inheritAttrs: false },
  Accordion: { template: '<div><slot /></div>' },
  AccordionTab: { template: '<div>{{ $attrs.header }}<slot /></div>', inheritAttrs: false },
  ProgressBar: { template: '<div class="pb" />' },
}

function mountWith(component: unknown, locale: Locale, props: Record<string, unknown>, extra: Record<string, unknown>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(component as never, {
    global: {
      plugins: [pinia, ConfirmationService, makeI18n(locale)],
      stubs: { ...TEXT_STUBS, ...((extra.stubs as object) || {}) },
      provide: extra.provide,
    },
    props,
  } as never)
}

/** 断言「zh-CN 与 en 的可见文案都命中」——即该文案确实来自 locales */
async function expectSwitches(
  component: unknown,
  props: Record<string, unknown>,
  zhText: string,
  enText: string,
  extra: Record<string, unknown> = {},
) {
  const zhWrapper = mountWith(component, 'zh-CN', props, extra)
  await flushPromises()
  expect(zhWrapper.text(), `zh-CN 未渲染「${zhText}」`).toContain(zhText)

  const enWrapper = mountWith(component, 'en', props, extra)
  await flushPromises()
  expect(enWrapper.text(), `en 未渲染「${enText}」`).toContain(enText)
}

describe('批 2 i18n：设置页文案随语言切换', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHttpGet.mockImplementation((url: string) => {
      if (url === '/adapter/config') return Promise.resolve({ data: ADAPTER_CONFIG })
      if (url === '/cache/stats') return Promise.resolve({ data: CACHE_STATS })
      if (url === '/wechat-ip/config') return Promise.resolve({ data: WECHAT_CONFIG })
      if (url === '/wechat-ip/status') return Promise.resolve({ data: WECHAT_STATUS })
      return Promise.resolve({ data: {} })
    })
  })

  it('themes.ts：四个主题名走 labelKey，三语均可解析且不回显 key', () => {
    const lookup = (messages: unknown, key: string) =>
      key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], messages)

    for (const theme of Object.values(THEMES)) {
      for (const [locale, messages] of [['zh-CN', zhCN], ['zh-TW', zhTW], ['en', en]] as const) {
        const value = lookup(messages, theme.labelKey)
        expect(typeof value, `${theme.id} 的 ${theme.labelKey} 在 ${locale} 缺失`).toBe('string')
        expect(value).not.toBe(theme.labelKey)
      }
    }
    // 简体 / 英文必须给出不同主题名（否则等于没翻译）
    expect(lookup(zhCN, THEMES.light.labelKey)).not.toBe(lookup(en, THEMES.light.labelKey))
  })

  it('SettingsTabSchema：卡片标题随语言切换', async () => {
    const { default: SettingsTabSchema } = await import('@/components/SettingsTabSchema.vue')
    await expectSwitches(SettingsTabSchema, { tabKey: 'storage' }, '存储设置', 'Storage Settings', {
      provide: { settingsSchemaTabs: { storage: [{ key: 'storage.root_dir' }] } },
      stubs: { DynamicSettingField: true },
    })
  })

  it('SettingsTabSystem：缓存/任务卡片标题随语言切换', async () => {
    const { default: SettingsTabSystem } = await import('./SettingsTabSystem.vue')
    await expectSwitches(SettingsTabSystem, { sections: { cacheManager: true, taskManager: true } }, '缓存管理', 'Cache Management', {
      stubs: { CacheManager: true, TaskManager: true },
    })
  })

  it('SettingsTabCircuit：熔断配置文案随语言切换', async () => {
    const { default: SettingsTabCircuit } = await import('./SettingsTabCircuit.vue')
    await expectSwitches(SettingsTabCircuit, {}, '失败阈值', 'Failure Threshold')
  })

  it('SettingsTabToken：API 令牌文案随语言切换', async () => {
    const { default: SettingsTabToken } = await import('./SettingsTabToken.vue')
    await expectSwitches(SettingsTabToken, {}, 'API 令牌', 'API Token')
  })

  it('SettingsTabUsers：用户管理文案随语言切换', async () => {
    const { default: SettingsTabUsers } = await import('./SettingsTabUsers.vue')
    await expectSwitches(SettingsTabUsers, {}, '用户管理', 'User Management')
  })

  it('CacheManager：缓存统计文案随语言切换', async () => {
    const { default: CacheManager } = await import('@/components/CacheManager.vue')
    await expectSwitches(CacheManager, {}, '使用量', 'Usage')
  })

  it('WechatTrustIP：可信 IP 文案随语言切换（第 173 行 C-2 状态值除外）', async () => {
    const { default: WechatTrustIP } = await import('@/components/WechatTrustIP.vue')
    await expectSwitches(WechatTrustIP, {}, '可信 IP 自动更新', 'Trusted IP Auto Update')
  })

  it('SettingsTabValidity：时效性 + 熔断区块标题随语言切换', async () => {
    const { default: SettingsTabValidity } = await import('./SettingsTabValidity.vue')
    await expectSwitches(SettingsTabValidity, {}, '时效性检查配置', 'Validity Check Config', {
      stubs: { ValidityConfig: true },
    })
  })

  it('SettingsTabAppearanceMixed：界面设置文案随语言切换', async () => {
    const { default: SettingsTabAppearanceMixed } = await import('@/components/SettingsTabAppearanceMixed.vue')
    await expectSwitches(
      SettingsTabAppearanceMixed,
      { selectedLocale: 'zh-CN', localeOptions: [], onUploadBg: () => {} },
      '界面设置',
      'Interface Settings',
      { provide: { settingsGetp: () => '', settingsSetp: () => {} } },
    )
  })

  it('DynamicSettingField：布尔选项「是/否」随语言切换', async () => {
    const { default: DynamicSettingField } = await import('@/components/DynamicSettingField.vue')
    const provide = {
      settingsSchema: { 'x.flag': { key: 'x.flag', field_type: 'toggle', default: false } },
      settingsConfig: { x: { flag: false } },
    }
    const zh = mountWith(DynamicSettingField, 'zh-CN', { fieldKey: 'x.flag' }, { provide })
    await flushPromises()
    expect(zh.text()).toContain('是')
    expect(zh.text()).toContain('否')

    const english = mountWith(DynamicSettingField, 'en', { fieldKey: 'x.flag' }, { provide })
    await flushPromises()
    expect(english.text()).toContain('Yes')
    expect(english.text()).toContain('No')
  })
})
