// PendingItemsCard：待确认列表 —— 首屏最多 6 条、"还有 N 项"、空态、source_site 兜底、总数回退
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PendingItemsCard from './PendingItemsCard.vue'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: mocks.get } }))

function items(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    standard_number: `GB/T ${1000 + i}`,
    standard_name: `标准 ${i + 1}`,
    source_site: i === 0 ? 'hbba' : undefined,
  }))
}

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(PendingItemsCard, { global: { plugins: [i18n] } })
}

describe('PendingItemsCard', () => {
  beforeEach(() => {
    mocks.get.mockReset()
  })

  it('加载中：不显示"全部处理完毕"空态（避免误报）', () => {
    mocks.get.mockReturnValue(new Promise(() => {}))
    const w = mountCard()
    expect(w.find('.empty').exists()).toBe(false)
    expect(w.find('.row').exists()).toBe(false)
  })

  it('成功：只渲染前 6 条，并显示 "还有 N 项..."', async () => {
    mocks.get.mockResolvedValueOnce({ data: { items: items(9), total: 9 } })
    const w = mountCard()
    await flushPromises()

    expect(mocks.get).toHaveBeenCalledWith('/pending', { routeTag: '/' })
    expect(w.findAll('.row')).toHaveLength(6)
    expect(w.text()).toContain('9 项待处理')
    expect(w.find('.more').text()).toContain('还有 3 项...')
  })

  it('total 不超过 6 时不显示"还有更多"', async () => {
    mocks.get.mockResolvedValueOnce({ data: { items: items(6), total: 6 } })
    const w = mountCard()
    await flushPromises()
    expect(w.find('.more').exists()).toBe(false)
  })

  it('空列表：显示"全部处理完毕"，总数为 0', async () => {
    mocks.get.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    const w = mountCard()
    await flushPromises()

    expect(w.find('.empty').exists()).toBe(true)
    expect(w.text()).toContain('全部处理完毕')
    expect(w.text()).toContain('0 项待处理')
  })

  it('行内 source_site 缺省时兜底 "STD"，standard_name 缺省不渲染 undefined', async () => {
    mocks.get.mockResolvedValueOnce({
      data: { items: [{ id: 1, standard_number: 'HB 1' }, { id: 2, standard_number: 'DB 2', source_site: 'csres' }], total: 2 },
    })
    const w = mountCard()
    await flushPromises()

    const rows = w.findAll('.row')
    expect(rows[0].find('.row-tag').text()).toBe('STD')
    expect(rows[0].find('.row-date').text()).toBe('')
    expect(rows[1].find('.row-tag').text()).toBe('csres')
    expect(w.text()).not.toContain('undefined')
  })

  it('total 缺失时回退为 items.length', async () => {
    mocks.get.mockResolvedValueOnce({ data: { items: items(8) } })
    const w = mountCard()
    await flushPromises()

    expect(w.text()).toContain('8 项待处理')
    expect(w.find('.more').text()).toContain('还有 2 项...')
  })

  it('接口失败：显示「加载失败」+ 重试，不得渲染「全部处理完毕」假空态（D-1 回归）', async () => {
    mocks.get.mockRejectedValueOnce(new Error('500'))
    const w = mountCard()
    await flushPromises()

    expect(w.text()).toContain('加载失败')
    expect(w.text()).not.toContain('全部处理完毕')

    // 重试：再次调用接口，成功则恢复列表
    mocks.get.mockResolvedValueOnce({ data: { items: items(2), total: 2 } })
    await w.find('.retry-link').trigger('click')
    await flushPromises()
    expect(w.findAll('.row')).toHaveLength(2)
  })
})
