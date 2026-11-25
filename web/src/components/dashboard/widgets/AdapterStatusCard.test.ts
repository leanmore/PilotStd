// AdapterStatusCard：适配器熔断表 —— 空态、状态标签/剩余秒数、未知状态告警、失败提示、
// 1s 倒计时与解冻后自动重载、手动刷新
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import AdapterStatusCard from './AdapterStatusCard.vue'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: mocks.get } }))

const ADAPTERS = [
  { name: 'csres', status: 'normal', frozen_until: null, remaining_seconds: 0, freeze_count: 1, fail_streak: 0 },
  { name: 'hbba', status: 'frozen', frozen_until: '2026-01-01', remaining_seconds: 30, freeze_count: 2, fail_streak: 4 },
  { name: 'gb', status: 'error', frozen_until: null, remaining_seconds: 0, freeze_count: 0, fail_streak: 0 },
]

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(AdapterStatusCard, { global: { plugins: [PrimeVue, i18n] } })
}

describe('AdapterStatusCard', () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue({ data: { adapters: ADAPTERS } })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('无适配器数据：显示空态，请求参数带首页路由标记', async () => {
    mocks.get.mockResolvedValueOnce({ data: { adapters: [] } })
    const w = mountCard()
    await flushPromises()

    expect(mocks.get).toHaveBeenCalledWith('/adapter/status', { routeTag: '/' })
    expect(w.find('.empty').text()).toBe('暂无适配器数据')
  })

  it('表格渲染：名称大写、状态标签语义、冻结剩余秒数（非冻结为 —）、冻结/失败次数', async () => {
    vi.useFakeTimers() // 冻结 1s 倒计时会改写剩余秒数，固定时钟保证断言 30s 稳定
    const w = mountCard()
    await flushPromises()

    const rows = w.findAll('tbody tr')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('CSRES')
    expect(rows[0].text()).toContain('正常')
    expect(rows[0].text()).toContain('—')
    expect(rows[1].text()).toContain('冻结中')
    expect(rows[1].text()).toContain('30s')
    expect(rows[1].text()).toContain('2')
    expect(rows[1].text()).toContain('4')
    expect(rows[2].text()).toContain('异常')
    expect(rows[1].find('.p-tag').classes()).toContain('p-tag-danger')
    expect(rows[2].find('.p-tag').classes()).toContain('p-tag-info')
  })

  it('未知状态：原样显示并打出开发者告警（便于发现后端新增枚举）', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mocks.get.mockResolvedValueOnce({ data: { adapters: [{ ...ADAPTERS[0], status: 'brand_new' }] } })
    const w = mountCard()
    await flushPromises()

    expect(w.text()).toContain('brand_new')
    expect(warn).toHaveBeenCalledWith('[AdapterStatusCard] 未映射的适配器状态:', 'brand_new')
  })

  it('拉取失败：显示错误文案，同时保留空态提示', async () => {
    mocks.get.mockRejectedValueOnce(new Error('500'))
    const w = mountCard()
    await flushPromises()

    expect(w.find('.err-msg').text()).toBe('加载适配器状态失败')
    expect(w.find('.empty').exists()).toBe(true)
  })

  it('每秒倒计时：冻结剩余秒数递减，解冻后自动重新拉取状态', async () => {
    vi.useFakeTimers()
    mocks.get.mockResolvedValue({ data: { adapters: [{ ...ADAPTERS[1], remaining_seconds: 1 }] } })
    const w = mountCard()
    await flushPromises()

    await vi.advanceTimersByTimeAsync(1000)
    await w.vm.$nextTick()
    expect(w.find('tbody tr').text()).toContain('0s')

    // 已到 0 且仍标记 frozen → tick 触发 loadStatus
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })

  it('点击刷新按钮重新加载；卸载后停止定时器', async () => {
    vi.useFakeTimers()
    const w = mountCard()
    await flushPromises()

    const refresh = w.findAll('.app-btn')[0]
    await refresh.trigger('click')
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(2)

    w.unmount()
    await vi.advanceTimersByTimeAsync(3000)
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })
})
