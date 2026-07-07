// views/AnnounceView.test.ts — 公告视图测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import AnnounceView from './AnnounceView.vue'
import zhCN from '@/locales/zh-CN.json'

const { getAnnounceResultsMock, postAnnounceCheckMock } = vi.hoisted(() => ({
  getAnnounceResultsMock: vi.fn(),
  postAnnounceCheckMock: vi.fn(),
}))

vi.mock('@/api', () => ({
  getAnnounceResults: getAnnounceResultsMock,
  postAnnounceCheck: postAnnounceCheckMock,
}))

// Mock /api/announce/stats（新版统计数据接口）
vi.mock('@/api/http', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: { total: { all: 2, gb: 1, hb: 1, db: 0 }, matched: 1, new: { all: 1, gb: 1, hb: 0, db: 0 } },
    }),
  },
}))

// Mock LogBar
vi.mock('@/components/LogBar.vue', () => ({
  default: { name: 'LogBar', template: '<div class="log-bar-stub" />' },
}))

function mountView() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(AnnounceView, {
    global: {
      plugins: [PrimeVue, i18n],
      stubs: {
        Calendar: { template: '<input class="calendar-stub" />', props: ['modelValue', 'locale', 'dateFormat', 'showIcon'] },
        Paginator: { template: '<div class="paginator-stub" />', props: ['rows', 'totalRecords'] },
        DataView: { template: '<div class="dataview-stub"><slot name="list" :items="value" /></div>', props: ['value', 'size'] },
      },
    },
  })
}

describe('AnnounceView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    getAnnounceResultsMock.mockResolvedValue({
      results: [
        { announce_no: '2026年第28号', announcement_title: '关于批准发布《纺织工业水污染物排放标准》等24项强制性国家标准的公告', standard_count: 25, publish_date: '2026-06-27', source_site: 'announcement_gb' },
        { announce_no: '2025年第1号', announcement_title: '2025年1月国家标准委收到北京市等27个省市区共发布标准1530项', standard_count: 1530, publish_date: '2025-02-01', source_site: 'announcement_db' },
      ],
    })
  })

  it('渲染三个胶囊标签（国家标准/行业标准/地方标准）', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const bar = wrapper.find('.unified-filter-bar')
    expect(bar.exists()).toBe(true)
    expect(bar.text()).toContain('国家标准')
    expect(bar.text()).toContain('行业标准')
    expect(bar.text()).toContain('地方标准')
  })

  it('渲染摘要标签', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('标准总数')
  })

  it('渲染"立即抓取"按钮', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('立即抓取')
  })

  it('无结果时正常渲染不崩溃', async () => {
    getAnnounceResultsMock.mockResolvedValue({ results: [] })
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.err-msg').exists()).toBe(false)
  })
})
