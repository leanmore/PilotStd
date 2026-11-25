// TaskTrendCard：标准库构成统计 —— 空态/有数据两种形态、总数聚合、四类语义色、拉取失败静默
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import TaskTrendCard from './TaskTrendCard.vue'
import { getStats } from '@/api'
import zhCN from '@/locales/zh-CN.json'

vi.mock('@/api', () => ({ getStats: vi.fn() }))

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(TaskTrendCard, { global: { plugins: [i18n] } })
}

describe('TaskTrendCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('空数据：显示空态提示，不渲染数字列表', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({ current: 0, expired: 0, pending: 0, upcoming: 0 })
    const w = mountCard()
    await flushPromises()

    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.text()).toContain('暂无标准数据')
    expect(w.text()).toContain('导入文件后自动统计')
    expect(w.find('.number-list').exists()).toBe(false)
  })

  it('有数据：总数聚合正确，四类指标名称与数值一一对应', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({ current: 10, expired: 2, pending: 3, upcoming: 5 })
    const w = mountCard()
    await flushPromises()

    expect(w.text()).toContain('20 条标准')
    const items = w.findAll('.list-item')
    expect(items).toHaveLength(4)
    expect(items.map((i) => i.find('.item-label').text())).toEqual(['现行', '废止', '待确认', '即将实施'])
    expect(items.map((i) => i.find('.item-value').text())).toEqual(['10', '2', '3', '5'])
  })

  it('四类指标使用固定语义色（绿/红/橙/蓝，跨主题一致）', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({ current: 1, expired: 1, pending: 1, upcoming: 1 })
    const w = mountCard()
    await flushPromises()

    const colors = w.findAll('.item-label').map((n) => (n.element as HTMLElement).style.color)
    // jsdom 会把十六进制色归一为 rgb()
    expect(colors).toEqual(['rgb(34, 197, 94)', 'rgb(239, 68, 68)', 'rgb(245, 158, 11)', 'rgb(59, 130, 246)'])
  })

  it('调用 getStats 时带首页路由标记 "/"，便于路由级取消', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({ current: 1, expired: 0, pending: 0, upcoming: 0 })
    mountCard()
    await flushPromises()
    expect(getStats).toHaveBeenCalledWith('/')
  })

  it('拉取失败：保持空态（catch 静默），不显示半截数据', async () => {
    vi.mocked(getStats).mockRejectedValueOnce(new Error('network'))
    const w = mountCard()
    await flushPromises()
    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.text()).toContain('0 条标准')
  })
})
