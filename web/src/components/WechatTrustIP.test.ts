// WechatTrustIP：配置/状态加载、保存与检测结果分支、Cookie 来源切换的条件渲染
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import WechatTrustIP from './WechatTrustIP.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppSelectButton from '@/components/ui/AppSelectButton.vue'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: mocks.get, put: mocks.put, post: mocks.post } }))

const CONFIG = {
  enabled: true, interval_hours: 6,
  ip_sources: ['https://myip.ipip.net'], cookie_source: 'manual',
  cookiecloud_url: '', cookiecloud_key: '', cookiecloud_password: '', cookie_status: '未配置',
  app_urls: '', use_selenium: true, headless: true, engine: 'auto',
  update_mode: 'append', notify_result: true, last_ip: '', last_check_at: '',
}
const STATUS = {
  current_ip: '1.2.3.4', current_ip_known: true, last_ip: '5.6.7.8',
  ip_changed: false, cookie_valid: true, enabled: true, last_check_at: '2026-01-01 10:00:00',
}

// Accordion 面板在 jsdom 下默认懒渲染；用透传替身保证两块配置内容都在 DOM 里可断言
const AccordionStub = defineComponent({ name: 'Accordion', template: '<div><slot /></div>' })
const AccordionTabStub = defineComponent({ name: 'AccordionTab', template: '<div class="tab-stub"><slot /></div>' })

function mountIp(config: Record<string, unknown> = {}, status: Record<string, unknown> = STATUS) {
  mocks.get.mockImplementation(async (url: string) => ({
    data: url.includes('/config') ? config : status,
  }))
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(WechatTrustIP, {
    global: {
      plugins: [PrimeVue, i18n],
      stubs: { Accordion: AccordionStub, AccordionTab: AccordionTabStub },
    },
  })
}

describe('WechatTrustIP', () => {
  beforeEach(() => {
    mocks.get.mockReset()
    mocks.put.mockReset().mockResolvedValue({ data: {} })
    mocks.post.mockReset().mockResolvedValue({ data: {} })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('挂载并加载配置/状态：标题、启用标签、当前 IP、上次 IP 与 Cookie 有效性', async () => {
    const w = mountIp(CONFIG)
    await flushPromises()

    expect(mocks.get).toHaveBeenCalledWith('/wechat-ip/config', { routeTag: '/settings' })
    expect(mocks.get).toHaveBeenCalledWith('/wechat-ip/status', { routeTag: '/settings' })
    const text = w.text()
    expect(text).toContain('可信 IP 自动更新')
    expect(text).toContain('已启用')
    expect(text).toContain('1.2.3.4')
    expect(text).toContain('5.6.7.8')
    expect(text).toContain('有效')
  })

  it('未探测到公网 IP（current_ip_known=false）时 Tag 降级为 secondary', async () => {
    const w = mountIp({ ...CONFIG, enabled: false }, { ...STATUS, current_ip: '', current_ip_known: false })
    await flushPromises()

    const tags = w.findAll('.p-tag')
    const unknownIpTag = tags.find((tag) => tag.text() === '') ?? tags.find((tag) => tag.classes().includes('p-tag-secondary'))
    expect(unknownIpTag).toBeTruthy()
    expect(w.text()).toContain('已停用')
  })

  it('配置加载失败：显示错误 Message（不是静默空白）', async () => {
    mocks.get.mockImplementation(async (url: string) => {
      if (url.includes('/config')) throw new Error('boom')
      return { data: STATUS }
    })
    const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
    const w = mount(WechatTrustIP, {
      global: {
        plugins: [PrimeVue, i18n],
        stubs: { Accordion: AccordionStub, AccordionTab: AccordionTabStub },
      },
    })
    await flushPromises()
    expect(w.text()).toContain('加载配置失败')
  })

  it('保存成功：PUT 携带完整配置 + 手动 Cookie 原文，并提示已保存、刷新状态', async () => {
    vi.useFakeTimers()
    const w = mountIp(CONFIG)
    await flushPromises()

    // 手动导入模式下最后一个 AppInput 是 Cookie HeaderString 文本域
    w.findAllComponents(AppInput).at(-1)!.vm.$emit('update:modelValue', 'k=v; x=y')
    await w.vm.$nextTick()
    const saveBtn = w.findAll('.app-btn').find((b) => b.text().includes('保存配置'))!
    await saveBtn.trigger('click')
    await flushPromises()

    const body = vi.mocked(mocks.put).mock.calls[0][1] as Record<string, unknown>
    expect(vi.mocked(mocks.put).mock.calls[0][0]).toBe('/wechat-ip/config')
    expect(body).toMatchObject({ enabled: true, interval_hours: 6, cookie_raw: 'k=v; x=y' })
    expect(w.text()).toContain('配置已保存')
    expect(mocks.get).toHaveBeenCalledWith('/wechat-ip/status', { routeTag: '/settings' })

    await vi.advanceTimersByTimeAsync(2000)
    expect(w.text()).not.toContain('配置已保存')
  })

  it('保存失败：优先展示后端 error，无 error 时回退"保存失败"', async () => {
    const w = mountIp(CONFIG)
    await flushPromises()
    const saveBtn = w.findAll('.app-btn').find((b) => b.text().includes('保存配置'))!

    mocks.put.mockRejectedValueOnce({ response: { data: { error: '后端拒绝' } } })
    await saveBtn.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('后端拒绝')

    mocks.put.mockRejectedValueOnce(new Error('network down'))
    await saveBtn.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('保存失败')
  })

  it('检测结果四种分支：updated / changed / same / error 各显示对应文案', async () => {
    const w = mountIp(CONFIG)
    await flushPromises()
    const checkBtn = w.findAll('.app-btn').find((b) => b.text().includes('检测并更新'))!

    const cases: Array<[Record<string, unknown>, string]> = [
      [{ updated: true, detected_ip: '9.9.9.9' }, '成功: IP 已更新为 9.9.9.9'],
      [{ changed: true, detected_ip: '8.8.8.8' }, '检测到 IP 变化: 8.8.8.8'],
      [{ detected_ip: '1.1.1.1' }, 'IP 未变化: 1.1.1.1'],
      [{ error: '无 Cookie' }, '失败: 无 Cookie'],
    ]
    for (const [data, expected] of cases) {
      mocks.post.mockResolvedValueOnce({ data })
      await checkBtn.trigger('click')
      await flushPromises()
      expect(w.text(), JSON.stringify(data)).toContain(expected)
    }
  })

  it('Cookie 来源在"手动导入/CookieCloud"之间切换时条件渲染对应字段', async () => {
    const w = mountIp(CONFIG)
    await flushPromises()
    expect(w.text()).toContain('Cookie (HeaderString 格式)')
    expect(w.text()).not.toContain('CookieCloud 服务地址')

    // 三个 AppSelectButton 依次为：更新模式 / 引擎 / Cookie 来源
    w.findAllComponents(AppSelectButton)[2].vm.$emit('update:modelValue', 'cookiecloud')
    await w.vm.$nextTick()

    expect(w.text()).toContain('CookieCloud 服务地址')
    expect(w.text()).toContain('用户密钥')
    expect(w.text()).not.toContain('Cookie (HeaderString 格式)')
  })
})
