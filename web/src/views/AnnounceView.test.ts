// views/AnnounceView.test.ts — 公告视图测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import { createPinia } from 'pinia'
import AnnounceView from './AnnounceView.vue'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import { setItem } from '@/lib/storage'

const { getAnnounceResultsMock, postAnnounceCheckMock, getAnnounceFetchFailuresMock } = vi.hoisted(() => ({
  getAnnounceResultsMock: vi.fn(),
  postAnnounceCheckMock: vi.fn(),
  getAnnounceFetchFailuresMock: vi.fn(),
}))

vi.mock('@/api', () => ({
  getAnnounceResults: getAnnounceResultsMock,
  postAnnounceCheck: postAnnounceCheckMock,
  getAnnounceFetchFailures: getAnnounceFetchFailuresMock,
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

function mountView(locale: 'zh-CN' | 'en' = 'zh-CN') {
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  return mount(AnnounceView, {
    global: {
      plugins: [PrimeVue, i18n, createPinia()],
      stubs: {
        Calendar: { template: '<input class="calendar-stub" />', props: ['modelValue', 'locale', 'dateFormat', 'showIcon'] },
        Paginator: { template: '<div class="paginator-stub" />', props: ['rows', 'totalRecords'] },
        DataView: { template: '<div class="dataview-stub"><slot name="list" :items="value" /></div>', props: ['value', 'size'] },
      },
    },
  })
}

// 公告抓取起点（含当日）：默认不得是“今天”，否则只覆盖当天（#89）
function localDateMinusDays(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function clickFetch(wrapper: ReturnType<typeof mountView>) {
  const btn = wrapper.findAll('button').find((b) => b.text().includes('立即抓取'))
  expect(btn).toBeTruthy()
  await btn!.trigger('click')
  await new Promise(r => setTimeout(r, 10))
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
    postAnnounceCheckMock.mockResolvedValue({ ok: true })
    getAnnounceFetchFailuresMock.mockResolvedValue({ total: 0, unresolved: 0, items: [] })
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

  it('有抓取失败时显示失败面板与未解决数（P1-03 读侧）', async () => {
    getAnnounceFetchFailuresMock.mockResolvedValue({
      total: 2,
      unresolved: 1,
      items: [{
        id: 1,
        task_type: 'scheduled',
        source_site: 'samr_gb',
        error_message: '网络超时',
        retry_count: 0,
        resolved: false,
        created_at: '2026-11-09 21:00:00',
        last_retry_at: null,
      }],
    })
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 20))
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('抓取失败')
    expect(wrapper.text()).toContain('1 条未解决')
    expect(wrapper.text()).toContain('网络超时')
  })

  it('列表刷新不按抓取日期过滤', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    // 列表请求不传 from_date：日期只用于“立即抓取”的起点
    expect(getAnnounceResultsMock).toHaveBeenCalledWith('announcement_gb', '', '/announce')

    const before = getAnnounceResultsMock.mock.calls.length
    const refresh = wrapper.findAll('button').find((b) => b.text().includes('刷新列表'))
    expect(refresh).toBeTruthy()
    await refresh!.trigger('click')
    await new Promise(r => setTimeout(r, 10))
    expect(postAnnounceCheckMock).toHaveBeenCalled()
    expect(getAnnounceResultsMock.mock.calls.length).toBe(before + 1)
  })

  it('无结果时正常渲染不崩溃', async () => {
    getAnnounceResultsMock.mockResolvedValue({ results: [] })
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.err-msg').exists()).toBe(false)
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', async () => {
    const zh = mountView('zh-CN')
    await new Promise(r => setTimeout(r, 10))
    expect(zh.text()).toContain('立即抓取')

    const english = mountView('en')
    await new Promise(r => setTimeout(r, 10))
    expect(english.text()).toContain('Fetch Now')
  })

  it('默认起始日期是最近 7 天，不是今天（否则只抓当天、漏历史）', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))

    await clickFetch(wrapper)

    expect(postAnnounceCheckMock.mock.calls[0][0]).toBe(localDateMinusDays(7))
    expect(postAnnounceCheckMock.mock.calls[0][0]).not.toBe(localDateMinusDays(0))
  })

  it('清空起始日期后不带 since_date（= 不限起点，全量历史补抓）', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))

    wrapper.findComponent({ name: 'AppCalendar' }).vm.$emit('update:modelValue', null)
    await new Promise(r => setTimeout(r, 10))

    await clickFetch(wrapper)

    expect(postAnnounceCheckMock.mock.calls[0][0]).toBeUndefined()
  })

  it('界面文案说明起始日期语义（含当日 + 清空=全量）', async () => {
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))

    expect(wrapper.find('.since-hint').exists()).toBe(true)
    expect(wrapper.find('.since-hint').text()).toContain('含当日')
    expect(wrapper.find('.since-hint').text()).toContain('清空')
  })

  it('沿用手选过的起始日期（localStorage 持久化）', async () => {
    setItem('announce_since', new Date('2024-03-05T00:00:00').toISOString())
    const wrapper = mountView()
    await new Promise(r => setTimeout(r, 10))

    await clickFetch(wrapper)

    expect(postAnnounceCheckMock.mock.calls[0][0]).toBe('2024-03-05')
  })
})
