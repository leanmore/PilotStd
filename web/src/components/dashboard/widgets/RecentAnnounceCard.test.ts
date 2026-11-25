// RecentAnnounceCard：最新公告分组 —— 骨架/空态、standard_type 分组与上限 3 条、默认激活非空 Tab、标题兜底
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Badge from 'primevue/badge'
import { createI18n } from 'vue-i18n'
import RecentAnnounceCard from './RecentAnnounceCard.vue'
import { getAnnounceResults } from '@/api'
import AppLoading from '@/components/ui/AppLoading.vue'
import zhCN from '@/locales/zh-CN.json'
import type { AnnounceItem } from '@/types/api'

vi.mock('@/api', () => ({ getAnnounceResults: vi.fn() }))

function item(no: string, type: AnnounceItem['standard_type'], over: Partial<AnnounceItem> = {}): AnnounceItem {
  return {
    announce_no: no,
    announcement_title: `公告 ${no}`,
    standard_count: 1,
    publish_date: '2026-01-01',
    source_site: 'gb',
    standard_type: type,
    ...over,
  }
}

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(RecentAnnounceCard, {
    global: {
      plugins: [PrimeVue, i18n],
      // 模板用的是 main.ts 里全局注册的 PrimeVue Tabs 族组件，测试需显式注册
      components: { Tabs, TabList, Tab, TabPanels, TabPanel, Badge },
    },
  })
}

describe('RecentAnnounceCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('加载中：渲染骨架加载态，不显示空态', () => {
    vi.mocked(getAnnounceResults).mockReturnValue(new Promise(() => {}))
    const w = mountCard()
    expect(w.findComponent(AppLoading).props('variant')).toBe('skeleton')
    expect(w.find('.empty').exists()).toBe(false)
  })

  it('按 standard_type 分组：每类最多 3 条，Tab 计数与排序固定', async () => {
    vi.mocked(getAnnounceResults).mockResolvedValueOnce({
      results: [
        item('g1', 'gb'), item('g2', 'gb'), item('g3', 'gb'), item('g4', 'gb'),
        item('h1', 'hb'), item('d1', 'db'),
      ],
    })
    const w = mountCard()
    await flushPromises()

    expect(getAnnounceResults).toHaveBeenCalledWith(undefined, undefined, '/')
    const labels = w.findAll('.p-tab').map((t) => t.text())
    // 默认激活第一个非空 Tab（national），该面板只渲染 3 条
    expect(w.findAll('.announce-item')).toHaveLength(3)
    expect(labels[0]).toContain('国家公告')
    expect(labels[0]).toContain('3')
    expect(labels[1]).toContain('行业公告')
    expect(labels[2]).toContain('地方公告')
  })

  it('默认激活跳过空分类：只有行业数据时直接展示行业公告', async () => {
    vi.mocked(getAnnounceResults).mockResolvedValueOnce({
      results: [item('h1', 'hb', { announcement_title: '行业公告一' })],
    })
    const w = mountCard()
    await flushPromises()

    expect(w.find('.announce-item').text()).toContain('行业公告一')
    // 空分类的 Tab 被禁用
    const tabs = w.findAll('.p-tab')
    expect(tabs[0].attributes('data-p-disabled')).toBe('true')
  })

  it('空结果：显示"暂无新公告"，不渲染 Tab', async () => {
    vi.mocked(getAnnounceResults).mockResolvedValueOnce({ results: [] })
    const w = mountCard()
    await flushPromises()

    expect(w.find('.empty').text()).toBe('暂无新公告')
    expect(w.find('.p-tab').exists()).toBe(false)
  })

  it('请求失败：降级为空态且不抛错', async () => {
    vi.mocked(getAnnounceResults).mockRejectedValueOnce(new Error('500'))
    const w = mountCard()
    await flushPromises()
    expect(w.find('.empty').exists()).toBe(true)
  })

  it('标题兜底：缺 announcement_title 用 announce_no，两者都缺显示"无标题"', async () => {
    vi.mocked(getAnnounceResults).mockResolvedValueOnce({
      results: [
        item('', 'gb', { announcement_title: '', announce_no: 'NO-1' }),
        item('', 'gb', { announcement_title: '', announce_no: '' }),
      ],
    })
    const w = mountCard()
    await flushPromises()

    const titles = w.findAll('.announce-item .title-text').map((n) => n.text())
    expect(titles).toEqual(['NO-1', '无标题'])
  })

  it('未知 standard_type 追加为末尾 Tab，不丢数据', async () => {
    vi.mocked(getAnnounceResults).mockResolvedValueOnce({
      results: [item('x1', 'mystery' as AnnounceItem['standard_type'])],
    })
    const w = mountCard()
    await flushPromises()

    // 固定 4 个内置分类 + 1 个动态追加分类
    const tabs = w.findAll('.p-tab')
    expect(tabs).toHaveLength(5)
    expect(tabs[4].text()).toContain('1')
    // 唯一的非空分类被默认激活，数据不丢
    expect(w.find('.announce-item').text()).toContain('公告 x1')
  })
})
