// `AnnounceView` 服务端分页回归测试（P0-3，2026-11-24）
//
// 修的缺陷：`page` 会从本地存储恢复（onPage 写入），刷新时 load() 按恢复的 page 取数，
// 但 `<Paginator>` 未绑 `:first` → Paginator 内部从 0 开始，高亮恒为第 1 页，
// 用户看到「内容已换页但页码没变」，误以为必须刷新浏览器。
//
// 本测试锁定契约：**Paginator 的 first 必须等于 page * rows**（含从存储恢复的场景）。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrimeVue from 'primevue/config'

import zhCN from '@/locales/zh-CN.json'

// 存储替身：内存 Map，便于在挂载前注入「已恢复的页码」
const memory = new Map<string, string>()
vi.mock('@/lib/storage', () => ({
  getItem: (k: string) => memory.get(k) ?? null,
  setItem: (k: string, v: string) => void memory.set(k, v),
  removeItem: (k: string) => void memory.delete(k),
}))

vi.mock('@/api', () => ({
  getAnnounceResults: vi
    .fn()
    .mockResolvedValue({
      results: [{ announce_no: 'A-1', source_site: 'announcement_gb', title: 'T', publish_date: '2026-01-01' }],
      total: 100,
    }),
  getAnnounceFetchFailures: vi.fn().mockResolvedValue({ total: 0, unresolved: 0, items: [] }),
  postAnnounceCheck: vi.fn().mockResolvedValue({ ok: true }),
}))
vi.mock('@/api/http', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { total: { all: 0, gb: 0, hb: 0, db: 0 }, new: { all: 0, gb: 0, hb: 0, db: 0 }, matched: 0, gb: 0, hb: 0, db: 0 } }) },
}))
vi.mock('@/stores/preferences', () => ({
  usePreferencesStore: () => ({ set: vi.fn().mockResolvedValue(undefined) }),
}))

import AnnounceView from './AnnounceView.vue'

function makeI18n() {
  return createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
}

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  await router.push('/announce')
  await router.isReady()
  return mount(AnnounceView, {
    global: {
      plugins: [makeI18n(), router, PrimeVue],
      directives: { tooltip: () => undefined },
      stubs: {
        UnifiedFilterBar: true,
        AppCalendar: true,
        LogBar: true,
        AnnounceRow: true,
      },
    },
  })
}

function paginatorFirst(wrapper: Awaited<ReturnType<typeof mountView>>): number {
  const pg = wrapper.findComponent({ name: 'Paginator' })
  expect(pg.exists(), '视图内应渲染 Paginator').toBe(true)
  return Number((pg.props() as { first?: number }).first ?? 0)
}

describe('AnnounceView 服务端分页：Paginator 第一行索引与当前页保持同步', () => {
  beforeEach(() => memory.clear())

  it('从存储恢复第 3 页（index=2）时，Paginator 的 first 应为 page*rows', async () => {
    memory.set('announce_page', '2')
    memory.set('announce_rows', '25')

    const wrapper = await mountView()
    await flushPromises()

    // page=2, rows=25 ⇒ 首行索引 50（第 3 页）
    expect(paginatorFirst(wrapper)).toBe(50)
    wrapper.unmount()
  })

  it('无存储值时按第 1 页（first=0）', async () => {
    const wrapper = await mountView()
    await flushPromises()

    expect(paginatorFirst(wrapper)).toBe(0)
    wrapper.unmount()
  })

  it('自定义每页条数也参与计算（page=1、rows=50 ⇒ first=50）', async () => {
    memory.set('announce_page', '1')
    memory.set('announce_rows', '50')

    const wrapper = await mountView()
    await flushPromises()

    expect(paginatorFirst(wrapper)).toBe(50)
    wrapper.unmount()
  })
})
