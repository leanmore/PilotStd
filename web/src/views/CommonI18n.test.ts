// web/src/views/CommonI18n.test.ts — 批 6 i18n 守卫：登录/注册/收藏/通用域文案随语言切换
//
// 覆盖原本**没有测试文件**的 RegisterView / RouteDebugPanel / TableLoadFooter /
// UnifiedFilterBar / LegacyRedirect，以及 router.ts 的 titleKey 路由元数据。
// 其余批 6 文件（FavoritesView / LoginView / BackupView / QueryHistory / SystemResources /
// LogBar / StandardTable / useFavorite / http.ts）在其既有测试文件里补了同类守卫。
// 做法同批 2~5：用真实 locale 文件挂载，空 messages 会让 t() 回显 key，因此断言能证明文案真的走 i18n。
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

// LegacyRedirect 只验模板文案：跳转目标由 useRoute/router 决定，这里 mock 掉取数
vi.mock('@/api/announce', () => ({
  getAnnouncementByNo: vi.fn().mockResolvedValue([]),
}))

type Locale = 'zh-CN' | 'zh-TW' | 'en'

/** 用真实 locale 文件挂载（空 messages 会让 t() 回显 key，断言即失去意义） */
function makeI18n(locale: Locale = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'NotFound', component: { template: '<div />' } },
      { path: '/:all(.*)', component: { template: '<div />' } },
    ],
  })
}

/** 只渲染文案的 PrimeVue stub（label/value/placeholder 走 $attrs，插槽原样透出） */
const TEXT_STUBS = {
  Button: { template: '<button>{{ $attrs.label }}<slot /></button>', inheritAttrs: false },
  ToggleSwitch: { template: '<div class="toggle-stub" />' },
  ProgressSpinner: { template: '<div />' },
}

function mountWith(component: unknown, locale: Locale, props: Record<string, unknown> = {}) {
  return mount(component as never, {
    props,
    global: { plugins: [makeI18n(locale), makeRouter()], stubs: TEXT_STUBS },
  } as never)
}

/** 断言「zh-CN / zh-TW / en 三语可见文案都命中，且没有 key 回显」 */
async function expectSwitches(
  component: unknown,
  texts: Record<Locale, string>,
  props: Record<string, unknown> = {},
  keyPrefix?: string,
) {
  for (const locale of ['zh-CN', 'zh-TW', 'en'] as const) {
    const wrapper = mountWith(component, locale, props)
    await flushPromises()
    expect(wrapper.text(), `${locale} 未渲染「${texts[locale]}」`).toContain(texts[locale])
    if (keyPrefix) {
      expect(wrapper.html(), `${locale} 出现 key 回显 ${keyPrefix}`).not.toContain(keyPrefix)
    }
    wrapper.unmount()
  }
}

describe('批 6 i18n：登录/注册/收藏/通用域文案随语言切换', () => {
  it('RegisterView：提示与提交按钮文案随语言切换', async () => {
    const { default: RegisterView } = await import('./RegisterView.vue')
    await expectSwitches(
      RegisterView,
      { 'zh-CN': '创建新账号', 'zh-TW': '建立新帳號', en: 'Create a new account' },
      {},
      'register.',
    )
  })

  it('RouteDebugPanel：标题与输入提示随语言切换', async () => {
    const { default: RouteDebugPanel } = await import('@/components/RouteDebugPanel.vue')
    await expectSwitches(
      RouteDebugPanel,
      { 'zh-CN': '路由调试', 'zh-TW': '路由除錯', en: 'Route Debug' },
      {},
      'route_debug.',
    )
  })

  it('TableLoadFooter：全部加载完成文案随语言切换', async () => {
    const { default: TableLoadFooter } = await import('@/components/TableLoadFooter.vue')
    await expectSwitches(
      TableLoadFooter,
      { 'zh-CN': '已显示全部 5 条标准', 'zh-TW': '已顯示全部 5 條標準', en: 'All 5 standards shown' },
      { displayed: 5, total: 5, isLoading: false, showLoadAllButton: false },
      'table_load.',
    )
  })

  it('UnifiedFilterBar：公告类型 labelKey 经 t() 翻译随语言切换', async () => {
    const { default: UnifiedFilterBar } = await import('@/components/UnifiedFilterBar.vue')
    await expectSwitches(
      UnifiedFilterBar,
      { 'zh-CN': '国家标准公告', 'zh-TW': '國家標準公告', en: 'National announcement' },
      { currentTab: 'gb', fetchEnabled: { gb: true, hb: false, db: false } },
      'announce.type_long.',
    )
  })

  it('LegacyRedirect：跳转中提示随语言切换', async () => {
    const { default: LegacyRedirect } = await import('./LegacyRedirect.vue')
    await expectSwitches(
      LegacyRedirect,
      { 'zh-CN': '正在跳转...', 'zh-TW': '正在跳轉...', en: 'Redirecting...' },
      {},
      'legacy.',
    )
  })

  // 批 6 把这两条路由的中文 title 兜底删掉、只留 titleKey —— 防止 key 拼错后侧边栏/标题退化成裸 key 或 path
  it('router.ts：公告详情/兼容跳转路由的 titleKey 在三语中均可解析', async () => {
    const { default: router } = await import('@/router')
    const cases: Array<[string, Record<Locale, string>]> = [
      ['/announce/:source/:announceNo', { 'zh-CN': '公告详情', 'zh-TW': '公告詳情', en: 'Announcement Detail' }],
      ['/announce/:announceNo', { 'zh-CN': '正在跳转...', 'zh-TW': '正在跳轉...', en: 'Redirecting...' }],
    ]
    for (const [path, expected] of cases) {
      const route = router.getRoutes().find((r) => r.path === path)
      expect(route, `router.ts 缺少路由 ${path}`).toBeTruthy()
      const titleKey = route!.meta.titleKey as string
      expect(titleKey, `${path} 未使用 titleKey`).toBeTruthy()
      expect(route!.meta.title, `${path} 不应再保留中文 title 兜底`).toBeUndefined()
      for (const locale of ['zh-CN', 'zh-TW', 'en'] as const) {
        const i18n = makeI18n(locale)
        expect(i18n.global.t(titleKey), `${locale} 的 ${titleKey} 未翻译`).toBe(expected[locale])
      }
    }
  })
})
