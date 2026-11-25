// SettingsTabToken 测试（API 令牌 + GitHub Token）
//
// 契约：挂载时并行加载「API 令牌」（getToken）与「GitHub Token」（GET /settings）；
// 令牌默认掩码（前 8 + **** + 后 4），可显隐/复制/确认后刷新；GitHub Token 保存走 PUT /settings。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { getToken, refreshToken } from '@/api'
import http from '@/api/http'
import SettingsTabToken from './SettingsTabToken.vue'

vi.mock('@/api', () => ({ getToken: vi.fn(), refreshToken: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))

const TOKEN = 'pst_1234567890abcdef'
const MASKED = 'pst_1234****cdef'

const AppDialog = {
  name: 'AppDialog',
  props: ['visible', 'header', 'modal', 'style'],
  emits: ['update:visible'],
  template: '<div class="dlg" v-if="visible"><slot /></div>',
}

function makeI18n() {
  return createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
}

function mountTab() {
  const wrapper = mount(SettingsTabToken, {
    global: { plugins: [PrimeVue, makeI18n()], stubs: { AppDialog } },
  })
  return wrapper
}

function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('SettingsTabToken API 令牌', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getToken).mockResolvedValue({ token: TOKEN })
    vi.mocked(refreshToken).mockResolvedValue({ token: 'pst_new_token_value_0001', refreshed_at: '' })
    vi.mocked(http.get).mockResolvedValue({ data: { updater: { github_token: '' } } } as never)
    vi.mocked(http.put).mockResolvedValue({ data: { ok: true } } as never)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('挂载即加载令牌与 GitHub Token，令牌默认以掩码展示', async () => {
    const wrapper = mountTab()
    await flushPromises()

    expect(getToken).toHaveBeenCalledWith('/settings')
    expect(http.get).toHaveBeenCalledWith('/settings', { routeTag: '/settings' })
    expect(wrapper.find('.token-value').text()).toBe(MASKED)
    // GitHub Token 为空 → 显示限流警告
    expect(wrapper.text()).toContain('未配置 GitHub Token')
  })

  it('点击显示后展示完整令牌，再点击恢复掩码', async () => {
    const wrapper = mountTab()
    await flushPromises()

    await button(wrapper, '显示完整令牌')!.trigger('click')
    expect(wrapper.find('.token-value').text()).toBe(TOKEN)
    await button(wrapper, '隐藏')!.trigger('click')
    expect(wrapper.find('.token-value').text()).toBe(MASKED)
  })

  it('已配置 GitHub Token 时回填输入框且不再显示警告', async () => {
    vi.mocked(http.get).mockResolvedValue({ data: { updater: { github_token: 'ghp_existing' } } } as never)
    const wrapper = mountTab()
    await flushPromises()

    const input = wrapper.find('input[type="password"]')
    expect((input.element as HTMLInputElement).value).toBe('ghp_existing')
    expect(wrapper.text()).not.toContain('未配置 GitHub Token')
  })

  it('保存 GitHub Token：PUT /settings 只带 updater.github_token 并提示已保存', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.find('input[type="password"]').setValue('ghp_new_value')
    await button(wrapper, '保存')!.trigger('click')
    await flushPromises()

    expect(http.put).toHaveBeenCalledWith('/settings', { updater: { github_token: 'ghp_new_value' } })
    expect(wrapper.text()).toContain('已保存')
  })

  it('复制令牌：写入剪贴板的是完整令牌而非掩码', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await button(wrapper, '复制')!.trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(TOKEN)
    expect(wrapper.text()).toContain('已复制到剪贴板')
  })

  it('刷新令牌需先确认：弹窗内「确定刷新」后才调用 refreshToken 并展示新令牌', async () => {
    const wrapper = mountTab()
    await flushPromises()

    await button(wrapper, '刷新令牌')!.trigger('click')
    expect(wrapper.find('.dlg').exists()).toBe(true)
    expect(refreshToken).not.toHaveBeenCalled()

    await button(wrapper, '确定刷新')!.trigger('click')
    await flushPromises()
    expect(refreshToken).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.token-value').text()).toBe('pst_new_token_value_0001')
  })

  it('加载令牌失败时显示错误提示（管理员权限要求）', async () => {
    vi.mocked(getToken).mockRejectedValue(new Error('403'))
    const wrapper = mountTab()
    await flushPromises()
    expect(wrapper.text()).toContain('加载令牌失败')
  })
})
