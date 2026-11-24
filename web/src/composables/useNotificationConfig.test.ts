// web/src/composables/useNotificationConfig.test.ts — 通知配置页 composable 单元测试
//
// NEW-44 补齐：此前 `useNotificationConfig.ts`（503 行）无任何测试。本文件锁定对外契约：
//   · 挂载即加载渠道 spec / 事件规格 / 配置 / 策略，并把表单回填为 spec 驱动结构
//   · spec_hash 内容级缓存：同哈希早退（保留用户编辑），force/hash 变化才重建；折叠态保留
//   · 两层订阅：策略层优先 config.json rules；空层默认全类别；旧逐事件列表补 task_progress
//   · 失败可见：配置加载/保存的错误文案（后端 error 优先 → i18n 兜底）、策略层失败单独标记、
//     策略层部分渠道写失败被收集（不谎报已保存）、静音时段失败仅警告
//   · 渲染辅助：i18n 缺键回退（标签/占位/徽标/分隔/类别/事件）与形态校验（partial/both/none）
//   · 保存链路：掩码字段增量提交、事件反推 rules、saved 提示 2s 复位、测试结果 4s 清理
// 依赖 @/api/notification 与用户偏好替身、vue-i18n 替身；生命周期靠 mount render-only 宿主触发，不挂 PrimeVue。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import type { ChannelSpec, ChannelFieldSpec } from '@/api/notification'

const mocks = vi.hoisted(() => ({
  getChannels: vi.fn(),
  getSpec: vi.fn(),
  getConfig: vi.fn(),
  getPolicies: vi.fn(),
  putConfig: vi.fn(),
  putPolicy: vi.fn(),
  putQuiet: vi.fn(),
  testNotif: vi.fn(),
  t: vi.fn(),
  te: vi.fn(),
  quietPrefs: { value: { enabled: false, start: '22:00', end: '07:00' } } as { value: { enabled: boolean; start: string; end: string } },
}))

vi.mock('@/api/notification', () => ({
  getNotificationChannels: mocks.getChannels,
  getNotificationSpec: mocks.getSpec,
  getNotificationConfig: mocks.getConfig,
  getNotificationPolicies: mocks.getPolicies,
  putNotificationConfig: mocks.putConfig,
  putNotificationPolicy: mocks.putPolicy,
  putQuietHours: mocks.putQuiet,
  testNotification: mocks.testNotif,
}))
vi.mock('@/composables/useUserPreferences', () => ({
  useUserPreferences: () => ({ quietHours: mocks.quietPrefs }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: mocks.t, te: mocks.te }) }))

import { useNotificationConfig } from './useNotificationConfig'

const I18N: Record<string, string> = {
  'notification.config.load_failed': '加载配置失败',
  'common.save_failed': '保存失败',
  'notification.config.testing': '测试中…',
  'notification.config.test_ok': '测试成功',
  'notification.config.test_failed': '测试失败：{msg}',
  'notification.config.unknown': '未知错误',
  'notification.config.required': '必填',
  'notification.config.optional': '可选',
  'notification.config.form.webhook': 'Webhook 形态',
  'notification.config.form.app': '自建应用形态',
  'notification.config.form.partial': '「{form}」还缺：{fields}',
  'notification.config.form.both_configured': '两种形态都已配置，将优先使用{form}',
  'notification.config.form.none_configured': '尚未配置完成（{forms}）',
  'notification.config.status.disabled': '未启用',
  'notification.config.status.configured': '已配置',
  'notification.config.status.pending': '待配置',
  'notification.config.class.task': '任务',
  'notification.event.archive_complete': '归档完成',
  'notification.field.webhook_url': 'Webhook 地址',
}

function field(name: string, over: Partial<ChannelFieldSpec> = {}): ChannelFieldSpec {
  const base: ChannelFieldSpec = { name, type: 'string', label_key: `notification.field.${name}`, label: name.toUpperCase(), required: true, mask: false, password: false, placeholder: '', placeholder_key: '', badge_key: '', form: 'webhook', divider_key: '' }
  return { ...base, ...over }
}

function spec(name: string, over: Partial<ChannelSpec> = {}): ChannelSpec {
  return {
    name, label_key: `notification.channel.${name}`, icon: 'pi pi-bell', enabled_default: false,
    hint_key: '', fields: [field('webhook_url', { mask: true }), field('secret')],
    forms: [{ key: 'webhook', label_key: 'notification.config.form.webhook', hint_key: '', required: ['webhook_url'], extra: ['secret'] }],
    status_rule: { branches: [{ all_of: ['webhook_url'], label_key: 'notification.config.status.configured' }], fallback_key: 'notification.config.status.pending' },
    ...over,
  }
}

const WECHAT = spec('wechat')
const TELEGRAM = spec('telegram', {
  fields: [field('bot_token', { form: '' })],
  forms: [],
  status_rule: { branches: [], fallback_key: 'notification.config.status.pending' },
})
const SPEC_EVENTS = ['archive_complete', 'task_progress', 'scan_failed']
const CHANNELS = {
  spec_hash: 'hash-1',
  channels: [WECHAT, TELEGRAM],
  notify_events: ['task', 'query'],
  event_class_map: { archive_complete: 'task', task_progress: 'task' },
}
const CONFIG = {
  enabled: true,
  channels: {
    wechat: { enabled: true, webhook_url: 'https://hook', secret: 'sec' },
    telegram: { enabled: false, bot_token: 'tok' },
  },
  rules: { archive_complete: ['wechat'] },
  quiet_hours: { enabled: true, start: '23:30', end: '06:15' },
}

let api: ReturnType<typeof useNotificationConfig>
let wrapper: ReturnType<typeof mount> | undefined

function mountConfig() {
  wrapper = mount(defineComponent({ setup: () => (api = useNotificationConfig()), render: () => h('div') }))
  return flushPromises().then(() => api)
}

/** 直接用测试夹具替换某渠道表单（helper 类用例不依赖 loadConfig 回填） */
const setForm = (name: string, fields: Record<string, string>, enabled = true) =>
  (api.channels.value[name] = { enabled, events: [], eventClasses: [], fields })

describe('useNotificationConfig', () => {
  beforeEach(() => {
    mocks.getChannels.mockReset().mockResolvedValue(CHANNELS)
    mocks.getSpec.mockReset().mockResolvedValue({ events: [...SPEC_EVENTS] })
    mocks.getConfig.mockReset().mockResolvedValue(CONFIG)
    mocks.getPolicies.mockReset().mockResolvedValue({ policies: [] })
    mocks.putConfig.mockReset().mockResolvedValue({ ok: true })
    mocks.putPolicy.mockReset().mockResolvedValue({ ok: true })
    mocks.putQuiet.mockReset().mockResolvedValue({ ok: true })
    mocks.testNotif.mockReset().mockResolvedValue({ ok: true })
    mocks.quietPrefs.value = { enabled: false, start: '22:00', end: '07:00' }
    mocks.t.mockReset().mockImplementation((key: string, params?: Record<string, unknown>) => {
      const raw = I18N[key] ?? key
      return params ? raw.replace(/\{(\w+)\}/g, (_m, name: string) => String(params[name] ?? '')) : raw
    })
    mocks.te.mockReset().mockImplementation((key: string) => key in I18N)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('挂载即加载 spec/config/策略并回填表单；初始默认值正确', async () => {
    await mountConfig()

    expect(mocks.getChannels).toHaveBeenCalledWith('/settings')
    expect(mocks.getSpec).toHaveBeenCalledWith('/settings')
    expect(mocks.getConfig).toHaveBeenCalledWith('/settings')
    expect([api.loading.value, api.saving.value, api.saved.value, api.errMsg.value]).toEqual([false, false, false, ''])
    expect([api.specHash.value, api.EVENTS.value]).toEqual(['hash-1', SPEC_EVENTS])
    expect([api.NOTIFY_EVENTS.value, api.EVENT_CLASS_MAP.value]).toEqual([CHANNELS.notify_events, CHANNELS.event_class_map])
    expect(api.enabled.value).toBe(true)
    expect(api.channels.value.wechat).toEqual({
      enabled: true, events: ['archive_complete'], eventClasses: [],
      fields: { webhook_url: 'https://hook', secret: 'sec' },
    })
    expect(api.channels.value.telegram).toEqual({
      enabled: false, events: [], eventClasses: [], fields: { bot_token: 'tok' },
    })
    expect([api.policyLoadFailed.value, api.policySaveFailures.value, api.testResults.value]).toEqual([false, [], {}])
    expect(api.channelOpen.value).toEqual({ wechat: false, telegram: false })
  })

  it('服务端静音时段为唯一真相：覆盖偏好并回填控件', async () => {
    await mountConfig()

    expect(mocks.quietPrefs.value).toEqual({ enabled: true, start: '23:30', end: '06:15' })
    expect(api.quietHoursEnabled.value).toBe(true)
    expect([api.quietHoursStart.value.getHours(), api.quietHoursStart.value.getMinutes()]).toEqual([23, 30])
    expect([api.quietHoursEnd.value.getHours(), api.quietHoursEnd.value.getMinutes()]).toEqual([6, 15])
  })

  it('策略层优先于 config.json rules；空层默认全类别；未知渠道策略忽略', async () => {
    mocks.getPolicies.mockResolvedValueOnce({
      policies: [
        { channel: 'wechat', events: ['scan_failed'], event_classes: ['task'] },
        { channel: 'telegram', events: [], event_classes: [] },
        { channel: 'email', events: ['x'], event_classes: [] },
      ],
    })
    await mountConfig()

    expect(api.channels.value.wechat).toMatchObject({ events: ['scan_failed'], eventClasses: ['task'] })
    expect(api.channels.value.telegram.events).toEqual([])
    expect(api.channels.value.telegram.eventClasses).toEqual(['task', 'query'])
  })

  it('策略层旧逐事件列表：类别层为空时自动并入 task_progress', async () => {
    mocks.getPolicies.mockResolvedValueOnce({
      policies: [{ channel: 'wechat', events: ['archive_complete'], event_classes: [] }],
    })
    await mountConfig()

    expect(api.channels.value.wechat.events).toEqual(['archive_complete', 'task_progress'])
  })

  it('策略层失败：policyLoadFailed 可见 + 开发者 warn，事件回退 config.json rules', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const err = new Error('policy down')
    mocks.getPolicies.mockRejectedValueOnce(err)
    await mountConfig()

    expect(api.policyLoadFailed.value).toBe(true)
    expect(warn).toHaveBeenCalledWith('[notification] policy API read failed; fell back to config.json rules', err)
    expect(api.channels.value.wechat.events).toEqual(['archive_complete'])
    expect([api.loading.value, api.errMsg.value]).toEqual([false, ''])
  })

  it('loadConfig 失败：后端 error 优先、无则 i18n 兜底；loading 收敛', async () => {
    mocks.getConfig.mockRejectedValueOnce({ response: { data: { error: '后端返回的错误' } } })
    await mountConfig()
    expect([api.errMsg.value, api.loading.value]).toEqual(['后端返回的错误', false])

    mocks.getConfig.mockRejectedValueOnce(new Error('network down'))
    await api.loadConfig()
    expect(api.errMsg.value).toBe('加载配置失败')
  })

  it('spec 尚未返回时 noChannelConfigured 不误报；加载后按渠道启用状态判定', async () => {
    mocks.getChannels.mockReturnValue(new Promise(() => {}))
    await mountConfig()
    expect([api.noChannelConfigured.value, api.loading.value]).toEqual([false, true])

    wrapper!.unmount()
    mocks.getChannels.mockResolvedValue(CHANNELS)
    await mountConfig()
    expect(api.noChannelConfigured.value).toBe(false)

    api.channels.value.wechat.enabled = false
    expect(api.noChannelConfigured.value).toBe(true)
    api.channels.value.telegram.enabled = true
    expect(api.noChannelConfigured.value).toBe(false)
  })

  it('loadChannelSpecs：同 spec_hash 早退不重建（保留编辑），仍刷新事件清单', async () => {
    await mountConfig()
    api.channels.value.wechat.fields.webhook_url = '用户输入'
    mocks.getSpec.mockResolvedValueOnce({ events: ['fresh_event'] })

    await api.loadChannelSpecs()

    expect(api.channels.value.wechat.fields.webhook_url).toBe('用户输入')
    expect(api.EVENTS.value).toEqual(['fresh_event'])
  })

  it('loadChannelSpecs(force) 强制重建并保留折叠态；hash 变化也重建', async () => {
    await mountConfig()
    api.channels.value.wechat.fields.webhook_url = '用户输入'
    api.channelOpen.value.wechat = true

    await api.loadChannelSpecs(true)
    expect(api.channels.value.wechat.fields.webhook_url).toBe('')
    expect(api.channelOpen.value.wechat).toBe(true)

    mocks.getChannels.mockResolvedValueOnce({ ...CHANNELS, spec_hash: 'hash-2', channels: [WECHAT] })
    await api.loadChannelSpecs()
    expect(api.specHash.value).toBe('hash-2')
    expect(Object.keys(api.channels.value)).toEqual(['wechat'])
  })

  it('fieldLabel/Placeholder/Badge/Divider：i18n 优先，缺键回退字面量或默认徽标', async () => {
    await mountConfig()
    const keyed = field('webhook_url', {
      placeholder_key: 'notification.config.required',
      badge_key: 'notification.config.optional',
      divider_key: 'notification.config.required',
    })

    expect([api.fieldLabel(keyed), api.fieldLabel(field('secret'))]).toEqual(['Webhook 地址', 'SECRET'])
    expect([api.fieldPlaceholder(keyed), api.fieldPlaceholder(field('secret', { placeholder: '请输入' }))]).toEqual(['必填', '请输入'])
    expect([api.fieldBadge(keyed), api.fieldBadge(field('secret'))]).toEqual(['可选', '必填'])
    expect([api.fieldBadge(field('secret', { required: false })), api.fieldDivider(field('secret'))]).toEqual(['可选', ''])
    expect(api.fieldDivider(keyed)).toBe('必填')
  })

  it('fieldsOfForm 按形态切分字段，未声明形态的字段归入通用区', async () => {
    await mountConfig()
    const mixed = spec('mixed', {
      fields: [field('webhook_url', { form: 'webhook' }), field('common', { form: '' })],
    })

    expect(api.fieldsOfForm(mixed, 'webhook').map((f) => f.name)).toEqual(['webhook_url'])
    expect(api.fieldsOfForm(mixed, '').map((f) => f.name)).toEqual(['common'])
    expect(api.fieldsOfForm(mixed, 'app')).toEqual([])
  })

  it('formIssues：一种都没配全/部分填写/两种都配全三种提示', async () => {
    await mountConfig()
    const multi = spec('dingtalk', {
      fields: [
        field('webhook_url', { form: 'webhook' }), field('secret', { form: 'webhook' }),
        field('corpid', { form: 'app' }), field('agentid', { form: 'app' }),
      ],
      forms: [
        { key: 'webhook', label_key: 'notification.config.form.webhook', hint_key: '', required: ['webhook_url'], extra: ['secret'] },
        { key: 'app', label_key: 'notification.config.form.app', hint_key: '', required: ['corpid', 'agentid'], extra: [] },
      ],
      status_rule: {
        branches: [
          { all_of: ['corpid', 'agentid'], label_key: 'notification.config.form.app' },
          { all_of: ['webhook_url'], label_key: 'notification.config.status.configured' },
        ],
        fallback_key: 'notification.config.status.pending',
      },
    })
    setForm(multi.name, { webhook_url: '', secret: '', corpid: '', agentid: '' })
    expect(api.formIssues(multi)).toEqual(['尚未配置完成（Webhook 形态 / 自建应用形态）'])

    setForm(multi.name, { webhook_url: 'https://x', secret: '', corpid: '', agentid: '' })
    expect(api.formIssues(multi)).toEqual([])

    setForm(multi.name, { webhook_url: 'https://x', secret: '', corpid: 'c', agentid: 'a' })
    expect(api.formIssues(multi)).toEqual(['两种形态都已配置，将优先使用自建应用形态'])

    setForm(multi.name, { webhook_url: '', secret: '', corpid: 'c', agentid: '' })
    expect(api.formIssues(multi)).toEqual(['「自建应用形态」还缺：AGENTID'])
  })

  it('statusText/statusSeverity：未启用/待配置/命中分支三段；i18n 缺键原样返回', async () => {
    await mountConfig()
    const ch = spec('dingtalk', {
      status_rule: {
        branches: [
          { all_of: ['webhook_url'], label_key: 'notification.config.status.configured' },
          { all_of: ['secret'], label_key: 'unknown.branch.key' },
        ],
        fallback_key: 'notification.config.status.pending',
      },
    })
    setForm(ch.name, {}, false)
    expect([api.statusText(ch), api.statusSeverity(ch)]).toEqual(['未启用', 'secondary'])

    api.channels.value[ch.name].enabled = true
    expect([api.statusText(ch), api.statusSeverity(ch)]).toEqual(['待配置', 'secondary'])

    api.channels.value[ch.name].fields.webhook_url = 'https://x'
    expect([api.statusText(ch), api.statusSeverity(ch)]).toEqual(['已配置', 'success'])

    api.channels.value[ch.name].fields.webhook_url = ''
    api.channels.value[ch.name].fields.secret = 's'
    expect(api.statusText(ch)).toBe('unknown.branch.key')
  })

  it('事件/类别标签与分组：未知键回退原值；channelHint 缺键返回空串', async () => {
    await mountConfig()

    expect([api.eventLabel('archive_complete'), api.eventLabel('brand_new')]).toEqual(['归档完成', 'brand_new'])
    expect([api.classLabel('task'), api.classLabel('mystery')]).toEqual(['任务', 'mystery'])
    expect(api.eventsOfClass('task')).toEqual(['archive_complete', 'task_progress'])
    expect(api.unmappedEvents()).toEqual(['scan_failed'])
    expect(api.channelHint(spec('x', { hint_key: 'notification.config.required' }))).toBe('必填')
    expect(api.channelHint(spec('x'))).toBe('')
  })

  it('saveConfig 成功：掩码字段增量提交、rules 反推、两层策略落库、saved 2s 复位', async () => {
    await mountConfig()
    vi.useFakeTimers()
    api.channels.value.wechat.fields.webhook_url = '****1234' // 掩码回显 → 不提交
    api.channels.value.wechat.fields.secret = 'secret-1'
    api.channels.value.wechat.events = ['archive_complete']
    api.channels.value.wechat.eventClasses = ['task']
    api.channels.value.telegram.events = ['archive_complete']

    await api.saveConfig()

    expect(mocks.putConfig).toHaveBeenCalledWith({
      enabled: true,
      channels: {
        wechat: { secret: 'secret-1', enabled: true, events: ['archive_complete'] },
        telegram: { bot_token: 'tok', enabled: false, events: ['archive_complete'] },
      },
      rules: { archive_complete: ['wechat', 'telegram'], task_progress: [], scan_failed: [] },
    })
    expect(mocks.putPolicy).toHaveBeenCalledWith({
      channel: 'wechat', events: ['archive_complete'], event_classes: ['task'],
    })
    expect(mocks.putPolicy).toHaveBeenCalledTimes(2)
    expect([api.saved.value, api.saving.value, api.errMsg.value]).toEqual([true, false, ''])

    await vi.advanceTimersByTimeAsync(2000)
    expect(api.saved.value).toBe(false)
  })

  it('saveConfig：策略层部分渠道写失败被收集并 warn，保存仍视为成功', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    await mountConfig()
    mocks.putPolicy.mockImplementation(async (payload: { channel: string }) => {
      if (payload.channel === 'wechat') throw new Error('policy write boom')
      return { ok: true }
    })

    await api.saveConfig()

    expect(api.policySaveFailures.value).toEqual(['wechat'])
    expect(warn).toHaveBeenCalledWith('[notification] policy layer write failed for channel wechat', expect.any(Error))
    expect([api.saved.value, api.saving.value]).toEqual([true, false])
  })

  it('saveConfig 失败：后端 error 优先、无则 i18n 兜底；不写策略层、saved 保持 false', async () => {
    await mountConfig()
    mocks.putConfig.mockRejectedValueOnce({ response: { data: { error: '保存被拒' } } })

    await api.saveConfig()
    expect([api.errMsg.value, api.saved.value, api.saving.value]).toEqual(['保存被拒', false, false])
    expect(mocks.putPolicy).not.toHaveBeenCalled()

    mocks.putConfig.mockRejectedValueOnce(new Error('network down'))
    await api.saveConfig()
    expect(api.errMsg.value).toBe('保存失败')
  })

  it('testChannel：测试中占位 → 成功/失败文案（响应与异常两条路径），4s 后清理结果', async () => {
    await mountConfig()
    vi.useFakeTimers()

    const pending = api.testChannel(WECHAT)
    expect(api.testResults.value.wechat).toBe('测试中…')
    await pending
    expect(api.testResults.value.wechat).toBe('测试成功')
    expect(mocks.testNotif).toHaveBeenCalledWith('wechat', { webhook_url: 'https://hook', secret: 'sec' })

    mocks.testNotif.mockResolvedValueOnce({ ok: false, error: 'boom' })
    await api.testChannel(WECHAT)
    expect(api.testResults.value.wechat).toBe('测试失败：boom')

    mocks.testNotif.mockResolvedValueOnce({ ok: false })
    await api.testChannel(WECHAT)
    expect(api.testResults.value.wechat).toBe('测试失败：未知错误')

    mocks.testNotif.mockRejectedValueOnce({ response: { data: { error: '服务端 500' } } })
    await api.testChannel(WECHAT)
    expect(api.testResults.value.wechat).toBe('测试失败：服务端 500')

    mocks.testNotif.mockRejectedValueOnce(new Error('socket closed'))
    await api.testChannel(WECHAT)
    expect(api.testResults.value.wechat).toBe('测试失败：socket closed')

    await vi.advanceTimersByTimeAsync(4000)
    expect(api.testResults.value.wechat).toBeUndefined()
  })

  it('saveQuietHours：写偏好 + 服务端；失败仅 warn，本地偏好保留', async () => {
    await mountConfig()
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    api.quietHoursEnabled.value = true
    api.quietHoursStart.value = new Date(2024, 0, 1, 23, 5)
    api.quietHoursEnd.value = new Date(2024, 0, 1, 6, 30)

    await api.saveQuietHours()
    expect(mocks.quietPrefs.value).toEqual({ enabled: true, start: '23:05', end: '06:30' })
    expect(mocks.putQuiet).toHaveBeenCalledWith({ enabled: true, start: '23:05', end: '06:30' })

    mocks.putQuiet.mockRejectedValueOnce(new Error('quiet down'))
    await api.saveQuietHours()
    expect(warn).toHaveBeenCalledWith('[notification] quiet hours save failed', expect.any(Error))
    expect(mocks.quietPrefs.value.enabled).toBe(true)
  })

  it('loadQuietHoursFromPrefs：按偏好字符串回填 Date，缺字段保持原值', async () => {
    await mountConfig()
    mocks.quietPrefs.value = { enabled: true, start: '21:45', end: '05:10' }

    api.loadQuietHoursFromPrefs()
    expect(api.quietHoursEnabled.value).toBe(true)
    expect([api.quietHoursStart.value.getHours(), api.quietHoursStart.value.getMinutes()]).toEqual([21, 45])
    expect([api.quietHoursEnd.value.getHours(), api.quietHoursEnd.value.getMinutes()]).toEqual([5, 10])

    api.quietHoursStart.value = new Date(2024, 0, 1, 12, 0)
    mocks.quietPrefs.value = { enabled: false, start: '', end: '' }
    api.loadQuietHoursFromPrefs()
    expect(api.quietHoursStart.value.getHours()).toBe(12)
  })
})
