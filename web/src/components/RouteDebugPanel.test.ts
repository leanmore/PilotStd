// RouteDebugPanel：查询校验（空词/非法 JSON）、请求体构造、结果渲染与错误兜底
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import RouteDebugPanel from './RouteDebugPanel.vue'
import AppInput from '@/components/ui/AppInput.vue'
import zhCN from '@/locales/zh-CN.json'

vi.mock('@/api/http', () => ({ default: { post: vi.fn(), get: vi.fn() } }))
import http from '@/api/http'

function mountPanel() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(RouteDebugPanel, { global: { plugins: [PrimeVue, i18n] } })
}

const inputs = (w: ReturnType<typeof mount>) => w.findAllComponents(AppInput)

/** 依次给查询词与模拟运行时 JSON 赋值（AppInput 受控，用 emit 走 v-model） */
async function fill(w: ReturnType<typeof mount>, query: string, runtimeJson = '') {
  inputs(w)[0].vm.$emit('update:modelValue', query)
  inputs(w)[1].vm.$emit('update:modelValue', runtimeJson)
  await w.vm.$nextTick()
}

describe('RouteDebugPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('查询词为空（含纯空格）时点击分析不发请求', async () => {
    const w = mountPanel()
    await fill(w, '   ')
    await w.find('.debug-btn').trigger('click')
    expect(http.post).not.toHaveBeenCalled()
  })

  it('正常查询：POST /query/debug 只带 query，结果按适配器/分数/原因渲染', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: [
        { adapter: 'csres', score: 90, reasons: ['prefix_match:GB/T'] },
        { adapter: 'hbba', score: 0, reasons: ['not_found'] },
      ],
    })
    const w = mountPanel()
    await fill(w, ' GB/T 1234 ')
    await w.find('.debug-btn').trigger('click')
    await flushPromises()

    expect(http.post).toHaveBeenCalledWith('/query/debug', { query: 'GB/T 1234' })
    const rows = w.findAll('.result-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].classes()).toContain('highlight')
    expect(rows[1].classes()).toContain('dimmed')
    expect(rows[0].text()).toContain('csres')
    expect(rows[0].text()).toContain('90')
    expect(rows[0].text()).toContain('prefix_match:GB/T')
  })

  it('合法运行时 JSON 作为 simulate_runtime 原样并入请求体', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ data: [] })
    const w = mountPanel()
    await fill(w, 'NB/T 1', '{"csres": {"daily_used": 200}}')
    await w.find('.debug-btn').trigger('click')
    await flushPromises()

    expect(http.post).toHaveBeenCalledWith('/query/debug', {
      query: 'NB/T 1',
      simulate_runtime: { csres: { daily_used: 200 } },
    })
  })

  it('非法运行时 JSON：提示格式错误且不请求后端', async () => {
    const w = mountPanel()
    await fill(w, 'GB/T 1', '{bad json')
    await w.find('.debug-btn').trigger('click')
    await flushPromises()

    expect(http.post).not.toHaveBeenCalled()
    expect(w.find('.error-msg').text()).toBe('JSON 格式错误，请检查 simulate_runtime')
  })

  it('请求失败：优先展示后端 detail', async () => {
    vi.mocked(http.post).mockRejectedValueOnce({ response: { data: { detail: '权限不足' } } })
    const w = mountPanel()
    await fill(w, 'GB/T 1')
    await w.find('.debug-btn').trigger('click')
    await flushPromises()

    expect(w.find('.error-msg').text()).toBe('权限不足')
  })

  it('请求失败且无 detail：回退 i18n "请求失败"', async () => {
    vi.mocked(http.post).mockRejectedValueOnce(new Error('network down'))
    const w = mountPanel()
    await fill(w, 'GB/T 1')
    await w.find('.debug-btn').trigger('click')
    await flushPromises()

    expect(w.find('.error-msg').text()).toBe('请求失败')
  })

  it('请求进行中：按钮进入禁用态并显示"分析中…"', async () => {
    let resolvePost!: (value: { data: unknown[] }) => void
    const pending = new Promise<{ data: unknown[] }>((resolve) => { resolvePost = resolve })
    vi.mocked(http.post).mockReturnValueOnce(pending)
    const w = mountPanel()
    await fill(w, 'GB/T 1')
    await w.find('.debug-btn').trigger('click')
    await w.vm.$nextTick()

    expect(w.find('.debug-btn').attributes('disabled')).toBeDefined()
    expect(w.find('.debug-btn').text()).toContain('分析中…')

    resolvePost({ data: [] })
    await flushPromises()
    expect(w.find('.debug-btn').text()).toContain('分析')
  })
})
