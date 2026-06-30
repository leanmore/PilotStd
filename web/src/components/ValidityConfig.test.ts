// components/ValidityConfig.test.ts — 时效性检查配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ValidityConfig from './ValidityConfig.vue'

const { getValidityConfigMock, putValidityConfigMock, runValidityCheckMock, getValidityHistoryMock } = vi.hoisted(() => ({
  getValidityConfigMock: vi.fn(),
  putValidityConfigMock: vi.fn(),
  runValidityCheckMock: vi.fn(),
  getValidityHistoryMock: vi.fn(),
}))

vi.mock('@/api/validity', () => ({
  getValidityConfig: getValidityConfigMock,
  putValidityConfig: putValidityConfigMock,
  runValidityCheck: runValidityCheckMock,
  getValidityHistory: getValidityHistoryMock,
}))

function mountValidityConfig() {
  return mount(ValidityConfig, {
    global: { plugins: [PrimeVue] },
  })
}

describe('ValidityConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getValidityConfigMock.mockResolvedValue({
      frequency: 'weekly', execute_time: '03:00', batch_size: 50,
      batch_interval: 5, check_ratio: 25, update_interval: 28,
    })
    getValidityHistoryMock.mockResolvedValue({
      total: 1, page: 1, page_size: 20,
      items: [{ check_date: '2026-06-28 03:00', checked_count: 100, changed_count: 3, status: 'success' }],
    })
  })

  it('渲染检查策略标题和表单字段', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('检查策略')
    expect(wrapper.html()).toContain('检查频率')
    expect(wrapper.html()).toContain('执行时间')
    expect(wrapper.html()).toContain('单批大小')
  })

  it('渲染"立即执行一次"按钮', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('立即执行一次')
  })

  it('渲染执行记录区域', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('执行记录')
  })

  it('加载失败时显示错误消息', async () => {
    getValidityConfigMock.mockRejectedValue({ response: { data: { error: '服务器错误' } } })
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('服务器错误')
  })

  it('执行记录中渲染数据行', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('2026-06-28')
    expect(html).toContain('100')
  })
})
