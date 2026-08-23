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

vi.mock('@/api/validity', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/validity')>()
  return {
    ...actual,
    getValidityConfig: getValidityConfigMock,
    putValidityConfig: putValidityConfigMock,
    runValidityCheck: runValidityCheckMock,
    getValidityHistory: getValidityHistoryMock,
  }
})

function mountValidityConfig() {
  return mount(ValidityConfig, {
    global: { plugins: [PrimeVue, i18n] },
  })
}

// script setup 顶层绑定暴露给测试的结构化形状（新增用例避免 as any 滥用）
interface ValidityVm {
  config: {
    total_weeks: number | null
    frequency_weeks: number | null
    check_ratio: number | null
    [key: string]: unknown
  }
  checkRatioDisplay: string
  onTotalOrFreqChange: () => void
  onCheckRatioChange: () => void
  isValid: boolean
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
    vm.onTotalOrFreqChange()
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

// ====== 三字段联动（总周期 T / 执行频率 F / 检查比例 P）—— 验收测试 14 用例映射 ======
// 组件层说明：PrimeVue InputNumber 在 blur 时 validateValue 强制 clamp 到 [min,max]，
// 因此"用户输入越界值 → 组件自动截断"（用例 #8/#13）由组件完成，测试中直接以截断后的值驱动 handler。
describe('ValidityConfig 三字段联动', () => {
  // 挂载后 config 被 mock 加载值覆盖：T=4, F=1, P=25
  async function mountLoaded() {
    const wrapper = mountValidityConfig()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    return wrapper
  }

  it('初始加载：T=4, F=1 → P=25，预览 25.0%（用例#1）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    expect(vm.config.total_weeks).toBe(4)
    expect(vm.config.frequency_weeks).toBe(1)
    expect(vm.config.check_ratio).toBe(25)
    expect(vm.checkRatioDisplay).toBe('25.0')
  })

  it('修改 T 保持 F 不变，重算 P：T=10, F=1 → P=10（用例#2）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.onTotalOrFreqChange()
    expect(vm.config.frequency_weeks).toBe(1)
    expect(vm.config.check_ratio).toBe(10)
    expect(vm.checkRatioDisplay).toBe('10.0')
  })

  it('修改 F 保持 T 不变，重算 P：T=10, F=2 → P=20（用例#3）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.frequency_weeks = 2
    vm.onTotalOrFreqChange()
    expect(vm.config.check_ratio).toBe(20)
    expect(vm.checkRatioDisplay).toBe('20.0')
  })

  it('修改 P 反推 F：T=10, P=25 → F=round(2.5)=3，P 回写 30（用例#4）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.check_ratio = 25
    vm.onCheckRatioChange()
    expect(vm.config.frequency_weeks).toBe(3)
    expect(vm.config.check_ratio).toBe(30)
  })

  it('修改 P 反推 F：T=10, P=80 → F=8，P=80（用例#5）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.check_ratio = 80
    vm.onCheckRatioChange()
    expect(vm.config.frequency_weeks).toBe(8)
    expect(vm.config.check_ratio).toBe(80)
  })

  it('P=.5 向上取整：T=10, P=95 → F=round(9.5)=10，P 回写 100（用例#6）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.check_ratio = 95
    vm.onCheckRatioChange()
    expect(vm.config.frequency_weeks).toBe(10)
    expect(vm.config.check_ratio).toBe(100)
  })

  it('修改 F 为 T：T=10, F=10 → P=100（用例#7）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.frequency_weeks = 10
    vm.onTotalOrFreqChange()
    expect(vm.config.check_ratio).toBe(100)
  })

  it('T 减小触发 F 截断：T=10→4（组件 min clamp），F=8 → F=4，P=100（用例#8）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    // 先进入 T=10, F=8, P=80 状态
    vm.config.total_weeks = 10
    vm.config.frequency_weeks = 8
    vm.onTotalOrFreqChange()
    // 模拟用户输入 2，PrimeVue blur 时 clamp 到 min=4
    vm.config.total_weeks = 4
    vm.onTotalOrFreqChange()
    expect(vm.config.frequency_weeks).toBe(4)
    expect(vm.config.check_ratio).toBe(100)
  })

  it('T 减小但 F 未越界则保持：T=10→4, F=3 → F=3，P=75（用例#9）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.frequency_weeks = 3
    vm.onTotalOrFreqChange()
    vm.config.total_weeks = 4
    vm.onTotalOrFreqChange()
    expect(vm.config.frequency_weeks).toBe(3)
    expect(vm.config.check_ratio).toBe(75)
  })

  it('小数精度：T=10, P=33.33 → F=round(3.333)=3，P 回写 30（用例#10）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.config.check_ratio = 33.33
    vm.onCheckRatioChange()
    expect(vm.config.frequency_weeks).toBe(3)
    expect(vm.config.check_ratio).toBe(30)
  })

  it('T 为最小值：T=4, F=2 → P=50（用例#11）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 4
    vm.config.frequency_weeks = 2
    vm.onTotalOrFreqChange()
    expect(vm.config.check_ratio).toBe(50)
  })

  it('连续操作：T→10, F→3, P→50 → 最终 T=10, F=5, P=50（用例#12）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.onTotalOrFreqChange()      // F=1 保持，P=10
    vm.config.frequency_weeks = 3
    vm.onTotalOrFreqChange()      // P=30
    vm.config.check_ratio = 50
    vm.onCheckRatioChange()       // F=round(5)=5，P 回写 50
    expect(vm.config.total_weeks).toBe(10)
    expect(vm.config.frequency_weeks).toBe(5)
    expect(vm.config.check_ratio).toBe(50)
  })

  it('T 超上限被组件 clamp 到 52：F=8 → P 按 T=52 重算（用例#13）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    // 模拟用户输入 999，PrimeVue blur 时 clamp 到 max=52
    vm.config.total_weeks = 52
    vm.config.frequency_weeks = 8
    vm.onTotalOrFreqChange()
    expect(vm.config.total_weeks).toBe(52)
    expect(vm.config.check_ratio).toBe(Math.round((8 / 52) * 10000) / 100)
  })

  it('T=52, F=52 → P=100，预览 100.0%（用例#14）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 52
    vm.config.frequency_weeks = 52
    vm.onTotalOrFreqChange()
    expect(vm.config.check_ratio).toBe(100)
    expect(vm.checkRatioDisplay).toBe('100.0')
  })

  it('清空输入（null）时联动安全跳过，不产生 NaN 污染', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    // PrimeVue allowEmpty=true：清空输入后 modelValue 为 null
    vm.config.total_weeks = null
    vm.onTotalOrFreqChange()
    expect(Number.isNaN(vm.config.check_ratio)).toBe(false)
    vm.config.total_weeks = 10
    vm.config.frequency_weeks = null
    vm.onTotalOrFreqChange()
    expect(Number.isNaN(vm.config.check_ratio)).toBe(false)
    vm.config.frequency_weeks = 1
    vm.config.check_ratio = null
    vm.onCheckRatioChange()
    expect(Number.isNaN(vm.config.frequency_weeks)).toBe(false)
  })

  it('联动幂等：重复触发 handler 不产生二次改动（isUpdating 保护）', async () => {
    const wrapper = await mountLoaded()
    const vm = wrapper.vm as unknown as ValidityVm
    vm.config.total_weeks = 10
    vm.onTotalOrFreqChange()
    // 联动回写 check_ratio 后，再次调用 handler 值已一致，不再改动任何字段
    vm.onTotalOrFreqChange()
    expect(vm.config.check_ratio).toBe(10)
    expect(vm.config.frequency_weeks).toBe(1)
  })
})
