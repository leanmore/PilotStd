// SettingsTabCircuit 测试
//
// 契约：挂载时从 `/adapter/config` 回填三个配置项（失败/被取消时不得抛错）；
// 保存前客户端校验「4 个阶梯时长严格递增、阈值/窗口 >= 1」，
// 通过后才 PUT 完整配置对象，再重新加载并给出「配置已保存」。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import http from '@/api/http'
import SettingsTabCircuit from './SettingsTabCircuit.vue'

vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))

const CFG = { failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 }

function makeI18n() {
  return createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
}

async function mountTab() {
  const wrapper = mount(SettingsTabCircuit, { global: { plugins: [PrimeVue, makeI18n()] } })
  await flushPromises()
  return wrapper
}

function inputs(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('input').map((i) => (i.element as HTMLInputElement).value)
}

describe('SettingsTabCircuit 熔断配置', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(http.get).mockResolvedValue({ data: JSON.parse(JSON.stringify(CFG)) } as never)
    vi.mocked(http.put).mockResolvedValue({ data: { ok: true } } as never)
  })

  it('挂载即请求配置并回填 6 个输入框（阈值/4 阶梯/归零窗口）', async () => {
    const wrapper = await mountTab()
    expect(http.get).toHaveBeenCalledWith('/adapter/config', { routeTag: '/settings' })
    expect(inputs(wrapper).slice(0, 6)).toEqual(['3', '30', '120', '360', '720', '24'])
  })

  it('请求被取消（响应 null）时不显示错误，保留默认值', async () => {
    vi.mocked(http.get).mockResolvedValue(null as never)
    const wrapper = await mountTab()
    expect(wrapper.text()).not.toContain('加载配置失败')
    expect(inputs(wrapper)[0]).toBe('3')
  })

  it('加载失败显示「加载配置失败」', async () => {
    vi.mocked(http.get).mockRejectedValue(new Error('boom'))
    const wrapper = await mountTab()
    expect(wrapper.text()).toContain('加载配置失败')
  })

  it('阶梯时长非严格递增时拒绝保存且不发 PUT', async () => {
    const wrapper = await mountTab()
    const vm = wrapper.vm as unknown as { circuitCfg: typeof CFG; saveCircuitConfig: () => Promise<void> }
    vm.circuitCfg.freeze_durations[1] = 10 // 10 <= 30，违反递增
    await vm.saveCircuitConfig()
    await flushPromises()

    expect(wrapper.text()).toContain('阶梯时长必须严格递增')
    expect(http.put).not.toHaveBeenCalled()
  })

  it('失败阈值 < 1 时拒绝保存', async () => {
    const wrapper = await mountTab()
    const vm = wrapper.vm as unknown as { circuitCfg: typeof CFG; saveCircuitConfig: () => Promise<void> }
    vm.circuitCfg.failure_threshold = 0
    await vm.saveCircuitConfig()
    await flushPromises()

    expect(wrapper.text()).toContain('失败阈值必须 >= 1')
    expect(http.put).not.toHaveBeenCalled()
  })

  it('校验通过后 PUT 完整配置、显示「配置已保存」并重新加载一次', async () => {
    const wrapper = await mountTab()
    const vm = wrapper.vm as unknown as { saveCircuitConfig: () => Promise<void> }
    await vm.saveCircuitConfig()
    await flushPromises()

    expect(http.put).toHaveBeenCalledWith('/adapter/config', CFG)
    expect(wrapper.text()).toContain('配置已保存')
    // 初始 1 次 + 保存后 1 次
    expect(http.get).toHaveBeenCalledTimes(2)
  })

  it('保存失败优先显示后端 error 字段', async () => {
    vi.mocked(http.put).mockRejectedValue({ response: { data: { error: '配置格式不合法' } } })
    const wrapper = await mountTab()
    await (wrapper.vm as unknown as { saveCircuitConfig: () => Promise<void> }).saveCircuitConfig()
    await flushPromises()
    expect(wrapper.text()).toContain('配置格式不合法')
  })
})
