// views/DashboardI18n.test.ts — 批 5 i18n 守卫：仪表板/布局文案随语言切换
//
// 覆盖原本**没有测试文件**的 12 个组件（AppHeader / AppSidebar / 9 个 widget / PlaceholderWidget / StatsCard）。
// AppLayout 与 AdapterStatusQueryCard 在各自测试里另有守卫，这里只做代表性覆盖。
// 做法同批 2/3/4：用真实 locale 文件挂载，空 messages 会让 t() 回显 key，因此断言能证明文案真的走 i18n。
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

vi.mock('@/api/http', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { adapters: [], stats: {}, logs: [], total: 0 } }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: { ok: true } }),
  },
}))
vi.mock('@/api', () => ({
  getStats: vi.fn().mockResolvedValue({ current: 0, expired: 0, pending: 0, upcoming: 0 }),
  getSettings: vi.fn().mockResolvedValue({}),
}))

type Locale = 'zh-CN' | 'zh-TW' | 'en'

function makeI18n(locale: Locale = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

/** 只渲染文案的 PrimeVue stub（label/value/header 走 $attrs，插槽原样透出） */
const TEXT_STUBS = {
  Button: { template: '<button>{{ $attrs.label }}<slot /></button>', inheritAttrs: false },
  Tag: { template: '<span class="tag">{{ $attrs.value }}<slot /></span>', inheritAttrs: false },
  Badge: { template: '<span class="badge">{{ $attrs.value }}<slot /></span>', inheritAttrs: false },
  Card: { template: '<div><slot name="title" /><slot name="content" /><slot /></div>' },
  DataTable: { template: '<div><slot /></div>' },
  Column: { template: '<div>{{ $attrs.header }}</div>', inheritAttrs: false },
  Dialog: { template: '<div>{{ $attrs.header }}<slot /></div>', inheritAttrs: false },
  Divider: { template: '<div />' },
  InputText: { template: '<input />' },
  Message: { template: '<div><slot /></div>' },
  ProgressBar: { template: '<div />' },
  ProgressSpinner: { template: '<div />' },
  Select: { template: '<div />' },
  Checkbox: { template: '<input type="checkbox" />' },
  Tabs: { template: '<div><slot /></div>' },
  TabList: { template: '<div><slot /></div>' },
  Tab: { template: '<div><slot /></div>' },
  TabPanels: { template: '<div><slot /></div>' },
  TabPanel: { template: '<div><slot /></div>' },
  AppCalendar: { template: '<div />' },
  TableLoadFooter: { template: '<div />' },
  FavoriteStatusTag: { template: '<div />' },
  LogBar: { template: '<div />' },
  NotificationBell: { template: '<div />' },
}

function mountWith(component: unknown, locale: Locale, props: Record<string, unknown> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:all(.*)', component: { template: '<div />' } }],
  })
  return mount(component as never, {
    global: { plugins: [pinia, makeI18n(locale), router], stubs: TEXT_STUBS },
    props,
  } as never)
}

async function expectSwitches(component: unknown, zhText: string, enText: string, props: Record<string, unknown> = {}) {
  const zhWrapper = mountWith(component, 'zh-CN', props)
  await flushPromises()
  expect(zhWrapper.text(), `zh-CN 未渲染「${zhText}」`).toContain(zhText)

  const enWrapper = mountWith(component, 'en', props)
  await flushPromises()
  expect(enWrapper.text(), `en 未渲染「${enText}」`).toContain(enText)
}

const W = (n: string) => import(`@/components/dashboard/widgets/${n}.vue`)

describe('批 5 i18n：仪表板/布局文案随语言切换', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('AppHeader：退出/主题/侧边栏提示文案随语言切换', async () => {
    const { default: AppHeader } = await import('@/components/AppHeader.vue')
    await expectSwitches(AppHeader, '退出', 'Log Out', {
      isMobile: false, sidebarCollapsed: false, pageTitle: 'Home', isDark: false, username: 'u',
    })
  })

  it('AppSidebar：折叠按钮文案随语言切换', async () => {
    const { default: AppSidebar } = await import('@/components/AppSidebar.vue')
    await expectSwitches(AppSidebar, '收起', 'Collapse', {
      sidebarCollapsed: false, navItems: [], routePath: '/',
    })
  })

  it('AdapterStatusCard：适配器状态文案随语言切换', async () => {
    const { default: C } = await W('AdapterStatusCard')
    await expectSwitches(C, '适配器状态', 'Adapter Status')
  })

  it('AdapterStatusAnnounceCard：公告适配器文案随语言切换', async () => {
    const { default: C } = await W('AdapterStatusAnnounceCard')
    await expectSwitches(C, '公告适配器', 'Announcement Adapter')
  })

  it('QuickActionsCard：快捷操作文案随语言切换', async () => {
    const { default: C } = await W('QuickActionsCard')
    await expectSwitches(C, '快捷操作', 'Quick Actions')
  })

  it('SystemInfoCard：系统状态文案随语言切换', async () => {
    const { default: C } = await W('SystemInfoCard')
    await expectSwitches(C, '系统状态', 'System Status')
  })

  it('TaskTrendCard：标准库构成文案随语言切换', async () => {
    const { default: C } = await W('TaskTrendCard')
    await expectSwitches(C, '标准库构成', 'Library Overview')
  })

  it('SystemLogCard：系统日志文案随语言切换', async () => {
    const { default: C } = await W('SystemLogCard')
    await expectSwitches(C, '系统日志', 'System Log')
  })

  it('AdapterStatusQueryCard：查询适配器集群标题随语言切换', async () => {
    const { default: C } = await W('AdapterStatusQueryCard')
    await expectSwitches(C, '查询适配器集群', 'Query Adapter Cluster')
  })

  it('RecentAnnounceCard：最新公告文案随语言切换', async () => {
    const { default: C } = await W('RecentAnnounceCard')
    await expectSwitches(C, '最新公告', 'Latest Announcements')
  })

  it('PendingItemsCard：待确认标准文案随语言切换', async () => {
    const { default: C } = await W('PendingItemsCard')
    await expectSwitches(C, '待确认标准', 'Pending Standards')
  })

  it('PlaceholderWidget：占位卡片文案随语言切换', async () => {
    const { default: C } = await W('PlaceholderWidget')
    await expectSwitches(C, '此卡片功能正在开发中', 'This card is under development', { widget: {} })
  })

  it('StatsCard：统计卡片文案随语言切换（不复现旧文案）', async () => {
    const { default: C } = await W('StatsCard')
    const zh = mountWith(C, 'zh-CN')
    await flushPromises()
    expect(zh.html()).not.toContain('dashboard.')
    const english = mountWith(C, 'en')
    await flushPromises()
    expect(english.html()).not.toContain('dashboard.')
  })
})
