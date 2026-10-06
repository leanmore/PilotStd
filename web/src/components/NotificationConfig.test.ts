// components/NotificationConfig.test.ts — 通知配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import NotificationConfig from './NotificationConfig.vue'

const {
  getNotificationConfigMock, putNotificationConfigMock, testNotificationMock,
  getNotificationChannelsMock, getNotificationSpecMock,
  getNotificationPoliciesMock, putNotificationPolicyMock,
} = vi.hoisted(() => ({
  getNotificationConfigMock: vi.fn(),
  putNotificationConfigMock: vi.fn(),
  testNotificationMock: vi.fn(),
  getNotificationChannelsMock: vi.fn(),
  getNotificationSpecMock: vi.fn(),
  // 阶段 4 · P6 · 4b：双层订阅与"吞错可见化"回归需要它们（默认值在 beforeEach 里给）
  getNotificationPoliciesMock: vi.fn(),
  putNotificationPolicyMock: vi.fn(),
}))

vi.mock('@/api/notification', () => ({
  getNotificationConfig: getNotificationConfigMock,
  putNotificationConfig: putNotificationConfigMock,
  testNotification: testNotificationMock,
  getNotificationChannels: getNotificationChannelsMock,
  getNotificationSpec: getNotificationSpecMock,
  getNotificationPolicies: getNotificationPoliciesMock,
  putNotificationPolicy: putNotificationPolicyMock,
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
    getNotificationPoliciesMock.mockResolvedValue({ policies: [] })
    putNotificationPolicyMock.mockResolvedValue({ ok: true })
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

  // ── 阶段 4 · P6 · 4b：双层订阅与缓存判据（用户点名的两条回归）────────────────────

  /** 带层级结构的渠道夹具：`notify_events` + `event_class_map` 随 spec_hash 一起变化 */
  function layerFixture(hash: string, classes: string[]) {
    return {
      ...CHANNEL_FIXTURE,
      spec_hash: hash,
      notify_events: classes,
      event_class_map: Object.fromEntries(classes.map(c => [`ev_for_${c}`, c])),
    }
  }

  it('层结构变化（spec_hash 变）⇒ 表单重建、新类别层可见；哈希未变则不重建', async () => {
    getNotificationChannelsMock.mockResolvedValue(layerFixture('hash-1', ['task_result']))
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(wrapper.html()).toContain('id="wechat-cls-task_result"')

    // ① 哈希未变 + 类别层变了（异常情形）⇒ 命中内容级缓存早退，**不重建**（证明缓存判据存在）
    getNotificationChannelsMock.mockResolvedValue(layerFixture('hash-1', ['task_result', 'security_alert']))
    await (wrapper.vm as unknown as { saveConfig: () => Promise<void> }).saveConfig()
    await wrapper.vm.$nextTick()
    expect(wrapper.html()).not.toContain('id="wechat-cls-security_alert"')

    // ② 哈希变化（层结构签名进哈希）=⇒ 重建，新类别层可见（这正是 4b-1 让层签名进 hash 的目的）
    getNotificationChannelsMock.mockResolvedValue(layerFixture('hash-2', ['task_result', 'security_alert']))
    await (wrapper.vm as unknown as { saveConfig: () => Promise<void> }).saveConfig()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(wrapper.html()).toContain('id="wechat-cls-security_alert"')
  })

  it('策略层写入失败 ⇒ UI 可见且不谎报（两类文案区分）', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    putNotificationPolicyMock.mockRejectedValue(new Error('policy api down'))
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await (wrapper.vm as unknown as { saveConfig: () => Promise<void> }).saveConfig()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    // 用户可见：明确点出"哪些渠道的策略层未落库"，不谎报全部成功
    expect(html).toContain('策略层未落库的渠道')
    // 开发者可见：ASCII console.warn（G-040 只允许用户文案走 t()）
    expect(warnSpy).toHaveBeenCalled()
    expect(String(warnSpy.mock.calls[0][0])).toContain('policy layer write failed')
    warnSpy.mockRestore()
  })

  it('策略读取失败 ⇒ 提示"策略服务读取失败"，与"策略为空"文案不同', async () => {    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    getNotificationPoliciesMock.mockRejectedValue(new Error('policy api down'))
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('策略服务读取失败')
    // "策略为空"时不得出现该失败提示（空策略是正常状态，默认 mock 即返回空）
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()

    warnSpy.mockClear()
    // 恢复正常返回（"策略为空"是正常状态）——先前的 mockRejectedValue 会一直生效到本次重置
    getNotificationPoliciesMock.mockResolvedValue({ policies: [] })
    const ok = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await ok.vm.$nextTick()
    await ok.vm.$nextTick()
    expect(ok.html()).not.toContain('策略服务读取失败')
  })

  // ── 阶段 3 · Step 2：形态分区展示 + 互斥校验 + 参数提示 ──────────────────────

  /** 双形态夹具（企微）：`forms` 声明序为 webhook→app，但 `status_rule` 分支序为 app→webhook，
   *  即"两者都配好时后端优先自建应用"——前端提示必须与之一致。 */
  function dualFormFixture() {
    return {
      ...CHANNEL_FIXTURE,
      channels: [
        {
          ...CHANNEL_FIXTURE.channels[0],
          name: 'wechat',
          fields: [
            { name: 'webhook_url', type: 'string', label_key: '', label: 'Webhook URL', required: false, mask: true, password: false, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '', form: 'webhook' },
            { name: 'corpid', type: 'string', label_key: '', label: 'CorpID', required: false, mask: false, password: false, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '', form: 'app' },
            { name: 'agentid', type: 'string', label_key: '', label: 'AgentID', required: false, mask: false, password: false, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '', form: 'app' },
            { name: 'corpsecret', type: 'text_password', label_key: '', label: 'Secret', required: false, mask: true, password: true, placeholder: '', placeholder_key: '', badge_key: '', divider_key: '', form: 'app' },
          ],
          forms: [
            { key: 'webhook', label_key: 'notification.config.form.webhook', hint_key: 'notification.config.form.webhook_hint', required: ['webhook_url'], extra: [] },
            { key: 'app', label_key: 'notification.config.form.app', hint_key: 'notification.config.form.app_hint', required: ['corpid', 'agentid', 'corpsecret'], extra: [] },
          ],
          status_rule: {
            branches: [
              { all_of: ['corpid', 'agentid', 'corpsecret'], label_key: 'notification.config.status.configured' },
              { all_of: ['webhook_url'], label_key: 'notification.config.status.configured' },
            ],
            fallback_key: 'notification.config.status.pending',
          },
        },
      ],
    }
  }

  async function mountDual(fill: Record<string, string>) {
    getNotificationChannelsMock.mockResolvedValue(dualFormFixture())
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    const vm = wrapper.vm as unknown as {
      channels: Record<string, { fields: Record<string, string> }>
      formIssues: (ch: unknown) => string[]
      fieldsOfForm: (ch: unknown, key: string) => unknown[]
    }
    Object.assign(vm.channels.wechat.fields, fill)
    await wrapper.vm.$nextTick()
    const ch = (getNotificationChannelsMock.mock.results[0].value as Promise<unknown>) && dualFormFixture().channels[0]
    return { wrapper, vm, ch }
  }

  it('双形态渠道：按形态分区渲染标题与提示（不是一条分隔线）', async () => {
    getNotificationChannelsMock.mockResolvedValue(dualFormFixture())
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    const html = wrapper.html()
    expect(html).toContain('form-section-title')
    expect(html).toContain('群机器人（Webhook）')
    expect(html).toContain('企业应用（自建应用）')
    expect(html).toContain('Webhook') // 形态提示文案
  })

  it('双形态渠道：只填一半 ⇒ 明确提示还缺哪些字段', async () => {
    getNotificationChannelsMock.mockResolvedValue(dualFormFixture())
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    const vm = wrapper.vm as unknown as {
      channels: Record<string, { fields: Record<string, string> }>
      formIssues: (ch: unknown) => string[]
    }
    vm.channels.wechat.fields.corpid = 'ww123'
    await wrapper.vm.$nextTick()
    const issues = vm.formIssues(dualFormFixture().channels[0])
    expect(issues.join(' ')).toContain('还缺')
    expect(issues.join(' ')).toContain('AgentID')
  })

  it('双形态渠道：两者都配全 ⇒ 提示优先使用的形态与后端分支序一致（自建应用）', async () => {
    getNotificationChannelsMock.mockResolvedValue(dualFormFixture())
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    const vm = wrapper.vm as unknown as {
      channels: Record<string, { fields: Record<string, string> }>
      formIssues: (ch: unknown) => string[]
    }
    Object.assign(vm.channels.wechat.fields, { webhook_url: 'https://qyapi/x', corpid: 'ww', agentid: '1', corpsecret: 's' })
    await wrapper.vm.$nextTick()
    const issues = vm.formIssues(dualFormFixture().channels[0]).join(' ')
    expect(issues).toContain('优先使用')
    expect(issues).toContain('企业应用（自建应用）')
  })

  it('双形态渠道：一个都没配全 ⇒ 提示不会被启用（如实告知，不谎报可用）', async () => {
    getNotificationChannelsMock.mockResolvedValue(dualFormFixture())
    const wrapper = mountConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    const vm = wrapper.vm as unknown as { formIssues: (ch: unknown) => string[] }
    const issues = vm.formIssues(dualFormFixture().channels[0]).join(' ')
    expect(issues).toContain('尚未配置完成')
  })
})
