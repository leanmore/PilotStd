// components/ValidityConfig.test.ts — 时效性检查配置组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import ValidityConfig from './ValidityConfig.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': {
      date: {
        weekday: {
          prefix: '周',
          short: { mon: '一', tue: '二', wed: '三', thu: '四', fri: '五', sat: '六', sun: '日' },
        },
      },
    },
    en: {
      date: {
        weekday: {
          prefix: '',
          short: { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' },
        },
      },
    },
  },
})

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
    global: { plugins: [PrimeVue, i18n] },
  })
}

describe('ValidityConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // ✅ #43: 更新 mock，包含 first_weekday 和 frequency_weeks
    getValidityConfigMock.mockResolvedValue({
      first_weekday: 1, execute_time: '03:00',
      total_weeks: 4, frequency_weeks: 1,
      batch_size: 50, batch_interval: 5, check_ratio: 25,
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
    // ✅ #43: 验证新字段渲染
    expect(wrapper.html()).toContain('首次执行')
    expect(wrapper.html()).toContain('总周期')
    expect(wrapper.html()).toContain('执行频率')
    expect(wrapper.html()).toContain('单批大小')
  })

  it('渲染自动计算结果区', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('执行次数')
    expect(wrapper.html()).toContain('每次覆盖')
    expect(wrapper.html()).toContain('首次执行时间')
  })

  // ✅ #43: 新增边界测试：frequency_weeks > total_weeks
  it('执行频率超过总周期时自动修正', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    vm.config.total_weeks = 4
    vm.config.frequency_weeks = 6
    vm.onFrequencyChange()
    expect(vm.config.frequency_weeks).toBe(4)
  })

  // ✅ #43: 新增边界测试：execution_count < 4 时保存按钮禁用
  it('执行次数不足4次时表单无效', async () => {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const vm = wrapper.vm as any
    vm.config.total_weeks = 4
    vm.config.frequency_weeks = 2  // 4/2 = 2 次 < 4
    await wrapper.vm.$nextTick()

    expect(vm.isValid).toBe(false)
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
