// web/src/views/FavoritesView.test.ts
// 收藏页状态列：必须显示**真实下载状态**的中文标签（而非 user_favorites 的英文原值）

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { createI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import FavoritesView from './FavoritesView.vue'
import zhCN from '@/locales/zh-CN.json'

// 组件在 main.ts 里是全局注册的（SFC 不 import），测试必须注册**同一套**：
// main.ts 注册的是 PrimeVue 4 的 Tabs/TabList/Tab/TabPanels/TabPanel，
// 若这里改成旧版 TabView，就会重现"测试绿、线上白"的盲区（2026-09-21 实测事故）。
const GLOBAL_COMPONENTS = { Button, Column, DataTable, Tag, Tabs, TabList, Tab, TabPanels, TabPanel }

// 本文件每个用例都要挂载一次完整收藏页（DataTable + Tabs），jsdom 下首次挂载
// 还要付模块求值成本；全量套件并行跑时实测超过 vitest 默认 5s，故显式放宽。
const MOUNT_TIMEOUT_MS = 20000

// 分类 Tab 数量：全部 + 国标 + 行标 + 地标 + 其他
const typeTabCount = 5

const LONG_ERROR = '采标标准，版权受限，自动跳过：' + 'x'.repeat(200)

function favorite(over: Record<string, unknown>) {
  return {
    id: 1,
    standard_number: 'GB 1-2026',
    std_name: '测试标准',
    standard_type: 'NationalStd',
    status: 'pending',
    local_path: null,
    publish_date: '2026-01-01',
    created_at: '2026-01-02T03:04:05',
    updated_at: '2026-01-02T03:04:05',
    source_site: null,
    download_status: null,
    download_error: null,
    last_attempt: null,
    download_updated_at: null,
    ...over,
  }
}

const FAVORITES = [
  favorite({ id: 1, standard_number: 'GB 1-2026', download_status: 'done', last_attempt: '2026-03-01' }),
  favorite({ id: 2, standard_number: 'GB 2-2026', download_status: 'failed', download_error: LONG_ERROR, last_attempt: '2026-03-02' }),
  favorite({ id: 3, standard_number: 'GB 3-2026', download_status: null }),
  favorite({ id: 4, standard_number: 'GB 4-2026', download_status: 'abandoned' }),
  favorite({ id: 5, standard_number: 'GB 5-2026', download_status: 'brand_new_status' }),
]

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ favorites: FAVORITES }) }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

async function mountView() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const wrapper = mount(FavoritesView, {
    global: { plugins: [PrimeVue, ToastService, i18n], components: GLOBAL_COMPONENTS },
  })
  await flushPromises()
  return wrapper
}

describe('FavoritesView 状态列', () => {
  it('按下载状态显示中文标签（不再直接渲染英文原值）', async () => {
    const wrapper = await mountView()
    const html = wrapper.html()

    expect(html).toContain('已归档')      // done
    expect(html).toContain('下载失败')    // failed
    expect(html).toContain('已放弃')      // abandoned
    expect(html).not.toContain('>pending<')  // 旧行为：直接渲染 user_favorites.status 原值
  }, MOUNT_TIMEOUT_MS)

  it('download_status 为 null（收藏但无队列行）显示"未加入队列"，不空白', async () => {
    const wrapper = await mountView()
    expect(wrapper.html()).toContain('未加入队列')
  }, MOUNT_TIMEOUT_MS)

  it('未知枚举值回退显示原文，不空白', async () => {
    const wrapper = await mountView()
    expect(wrapper.html()).toContain('brand_new_status')
  }, MOUNT_TIMEOUT_MS)

  it('失败原因展示截断，全量留在 title 里供悬停查看', async () => {
    const wrapper = await mountView()
    const html = wrapper.html()

    // 正文里是截断后的（120 字符 + 省略号）
    expect(html).toContain(LONG_ERROR.slice(0, 120) + '…')
    // 全量只出现在 title 属性中（悬停可见），不在正文里重复铺开
    expect(html).toContain(`title="${LONG_ERROR}"`)
  }, MOUNT_TIMEOUT_MS)
})

// 回归守卫：2026-09-21 线上实测发现 <TabView> 未在 main.ts 注册（v4 已改名 Tabs），
// 5 个 TabPanel 全部平铺 → 同一批数据渲染 5 张表、无 Tab 切换器、页面高 2 万像素。
describe('FavoritesView 分类 Tab 容器', () => {
  it('只渲染一张表，行数等于接口返回条数', async () => {
    const wrapper = await mountView()

    expect(wrapper.findAll('table')).toHaveLength(1)
    expect(wrapper.findAll('table tbody tr')).toHaveLength(FAVORITES.length)
    // 未解析的组件会以自定义元素残留在 DOM 里
    expect(wrapper.find('tabview').exists()).toBe(false)
  }, MOUNT_TIMEOUT_MS)

  it('渲染 Tab 切换器与分类计数（含默认活动面板）', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('[role="tablist"]').exists()).toBe(true)
    expect(wrapper.findAll('[role="tab"]')).toHaveLength(typeTabCount)
    expect(wrapper.find('[role="tabpanel"]').exists()).toBe(true)
    // 标题带上分类计数：全部 5 条
    expect(wrapper.find('[role="tablist"]').text()).toContain(`全部 (${FAVORITES.length})`)
  }, MOUNT_TIMEOUT_MS)
})
