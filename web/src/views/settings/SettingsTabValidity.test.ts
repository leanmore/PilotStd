// SettingsTabValidity 测试
//
// Q16 后本 Tab 同时承载「时效性检查配置」（子组件 ValidityConfig）与「熔断配置」。
// 契约：两个区块都可折叠；熔断配置的加载/校验/保存逻辑与独立 Tab（SettingsTabCircuit）一致；
// defineExpose 的 doSave 必须转发到 ValidityConfig.doSave，否则父组件「应用」按钮保存不到时效性配置。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import http from '@/api/http'
import SettingsTabValidity from './SettingsTabValidity.vue'

vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))

const CFG = { failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 }

function makeI18n() {
  return createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
}

function mountTab() {
  const validityDoSave = vi.fn()
  const ValidityConfig = {
    name: 'ValidityConfig',
    template: '<div class="validity-stub" />',
    methods: { doSave: validityDoSave },
  }
  const wrapper = mount(SettingsTabValidity, {
    global: { plugins: [PrimeVue, makeI18n()], stubs: { ValidityConfig } },
  })
  return { wrapper, validityDoSave }
}

describe('SettingsTabValidity 时效性 + 熔断', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(http.get).mockResolvedValue({ data: JSON.parse(JSON.stringify(CFG)) } as never)
    vi.mocked(http.put).mockResolvedValue({ data: { ok: true } } as never)
  })

  it('挂载即加载熔断配置并回填输入框', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/adapter/config', { routeTag: '/settings' })
    const values = wrapper.findAll('input').map((i) => (i.element as HTMLInputElement).value)
    expect(values.slice(0, 6)).toEqual(['3', '30', '120', '360', '720', '24'])
  })

  it('加载失败显示「加载配置失败」，不影响时效性子区块渲染', async () => {
    vi.mocked(http.get).mockRejectedValue(new Error('boom'))
    const { wrapper } = mountTab()
    await flushPromises()
    expect(wrapper.text()).toContain('加载配置失败')
    expect(wrapper.find('.validity-stub').exists()).toBe(true)
  })

  it('阶梯非递增时拒绝保存且不发 PUT，显示校验错误', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    const vm = wrapper.vm as unknown as { circuitCfg: typeof CFG; saveCircuitConfig: () => Promise<void> }
    vm.circuitCfg.freeze_durations = [30, 10, 360, 720]
    await vm.saveCircuitConfig()
    await flushPromises()

    expect(wrapper.text()).toContain('阶梯时长必须严格递增')
    expect(http.put).not.toHaveBeenCalled()
  })

  it('校验通过后 PUT 完整配置并提示已保存', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    await (wrapper.vm as unknown as { saveCircuitConfig: () => Promise<void> }).saveCircuitConfig()
    await flushPromises()

    expect(http.put).toHaveBeenCalledWith('/adapter/config', CFG)
    expect(wrapper.text()).toContain('配置已保存')
  })

  it('defineExpose.doSave 转发到 ValidityConfig.doSave', async () => {
    const { wrapper, validityDoSave } = mountTab()
    ;(wrapper.vm as unknown as { doSave: () => void }).doSave()
    expect(validityDoSave).toHaveBeenCalledTimes(1)
  })

  it('折叠头切换两个区块的显隐（rules / circuit）', async () => {
    const { wrapper } = mountTab()
    await flushPromises()
    const headers = wrapper.findAll('.collapsible-header')
    expect(headers.length).toBe(2)

    // transition + v-show 的离场在 jsdom 里不触发 transitionend，故直接读 style.display
    const collapsed = (i: number) =>
      ((wrapper.findAll('.collapsible-content')[i].attributes('style') || '').includes('display: none'))

    expect(collapsed(0)).toBe(false)
    await headers[0].trigger('click')
    await flushPromises()
    expect(collapsed(0)).toBe(true)

    expect(collapsed(1)).toBe(false)
    await headers[1].trigger('click')
    await flushPromises()
    expect(collapsed(1)).toBe(true)
  })
})
