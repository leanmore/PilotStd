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
        { type: 'gb', std_code: 'GB/T 1.1-2020', std_name: '标准化工作导则', replaces_code: 'GB/T 1.1-2009', publish_date: '2020-03-31' },
        { type: 'gb', std_code: 'GB 15979-2024', std_name: '一次性使用卫生用品卫生标准', replaces_code: null, publish_date: '2024-06-01' },
      ],
      summary: { total_standards: 2, matched: 1, updated: 0, new: 1, skipped: 0 },
      last_check: '2026-06-29 12:00',
    })
  })

  it('渲染三个 tab 标签（国家标准/行业标准/地方标准）', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const tabsEl = wrapper.find('.tabs')
    expect(tabsEl.exists()).toBe(true)
    expect(tabsEl.text()).toContain('国家标准')
    expect(tabsEl.text()).toContain('行业标准')
    expect(tabsEl.text()).toContain('地方标准')
  })

  it('渲染摘要标签', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('标准总数')
  })

  it('渲染"立即检查"按钮', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('立即检查')
  })

  it('无结果时正常渲染不崩溃', async () => {
    getAnnounceResultsMock.mockResolvedValue({ results: [], summary: {}, last_check: '' })
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.err-msg').exists()).toBe(false)
  })
})
