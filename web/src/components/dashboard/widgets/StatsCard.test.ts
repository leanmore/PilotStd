// StatsCard：核心统计 —— 骨架加载、四指标渲染、失败降级为 "—"、null 字段回退 0
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import StatsCard from './StatsCard.vue'
import { getStats } from '@/api'
import zhCN from '@/locales/zh-CN.json'

vi.mock('@/api', () => ({ getStats: vi.fn() }))

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(StatsCard, { global: { plugins: [i18n] } })
}

describe('StatsCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('加载中：渲染 1 个主骨架 + 3 个副骨架，不显示数字', () => {
    vi.mocked(getStats).mockReturnValue(new Promise(() => {}))
    const w = mountCard()

    expect(w.find('.mp-skeleton-main').exists()).toBe(true)
    expect(w.findAll('.mp-skeleton-sub')).toHaveLength(3)
    expect(w.find('.mp-hero-value').exists()).toBe(false)
  })

  it('成功：主指标取 current，三个副指标分别取 pending/upcoming/expired', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({ current: 42, expired: 3, pending: 7, upcoming: 9 })
    const w = mountCard()
    await flushPromises()

    expect(w.find('.mp-hero-label').text()).toBe('现行')
    expect(w.find('.mp-hero-value').text()).toBe('42')
    const minis = w.findAll('.mp-mini-card')
    expect(minis.map((m) => m.find('.mp-mini-label').text())).toEqual(['待确认', '即将实施', '废止'])
    expect(minis.map((m) => m.find('.mp-mini-val').text())).toEqual(['7', '9', '3'])
    expect(w.text()).toContain('有效')
  })

  it('失败：四个指标统一降级为 "—"，不展示 0 误导用户', async () => {
    vi.mocked(getStats).mockRejectedValueOnce(new Error('500'))
    const w = mountCard()
    await flushPromises()

    expect(w.find('.mp-hero-value').text()).toBe('—')
    expect(w.findAll('.mp-mini-val').map((n) => n.text())).toEqual(['—', '—', '—'])
    expect(w.find('.mp-skeleton-main').exists()).toBe(false)
  })

  it('后端返回 null 字段时回退 0（?? 兜底）', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({
      current: null, expired: undefined, pending: 2, upcoming: null,
    } as unknown as { current: number; expired: number; pending: number; upcoming: number })
    const w = mountCard()
    await flushPromises()

    expect(w.find('.mp-hero-value').text()).toBe('0')
    expect(w.findAll('.mp-mini-val').map((n) => n.text())).toEqual(['2', '0', '0'])
  })

  it('成功拉取后骨架消失，只剩真实内容', async () => {
    vi.mocked(getStats).mockResolvedValueOnce({ current: 1, expired: 1, pending: 1, upcoming: 1 })
    const w = mountCard()
    await flushPromises()
    expect(w.find('.mp-skeleton-main').exists()).toBe(false)
    expect(w.findAll('.mp-mini-card')).toHaveLength(3)
  })
})
