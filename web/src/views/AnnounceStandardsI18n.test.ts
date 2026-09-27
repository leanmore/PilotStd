// views/AnnounceStandardsI18n.test.ts — 批 4 i18n 守卫：公告详情 / 标准状态文案随语言切换
//
// 覆盖原本**没有测试文件**的 AnnounceDetail.vue 与 StandardsStatusView.vue。
// AnnounceDetail 的取数/解析/收藏全在 useAnnounceDetail 里，此处**按需 mock 掉该 composable**，
// 使断言只针对**组件自身模板里的 t() 调用**（composable 的 key 映射由「动态 key 存在性探针」覆盖，见批 4 报告）。
// 做法同批 2/3：用真实 locale 文件挂载，空 messages 会让 t() 回显 key，因此断言能证明文案真的走 i18n。
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { computed, ref } from 'vue'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import ToastService from 'primevue/toastservice'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

vi.mock('@/api/standards', () => ({
  getStandardsStats: vi.fn().mockResolvedValue({ active: 0, inactive: 0, unknown: 0 }),
  getStandardsStatus: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  clearStandardsStatusCache: vi.fn(),
}))

// 增量滚动与"文案是否走 i18n"无关，整体 mock 掉以避免其内部异步/边界噪音
vi.mock('@/composables/useIncrementalScroll', () => ({
  useIncrementalScroll: () => ({
    displayRecords: ref([]),
    isLoadingMore: ref(false),
    showLoadAllButton: ref(false),
    loadAllRemaining: vi.fn(),
    totalCount: ref(0),
    reload: vi.fn(),
  }),
}))

// AnnounceDetail 只验模板文案：把 composable 整体 mock（含 statusLabelKey → 真 key，验证 t() 链路）
vi.mock('@/composables/useAnnounceDetail', () => ({
  useAnnounceDetail: () => ({
    loading: ref(false),
    parsing: ref(false),
    announcement: ref({ announce_no: 'A-1', source_type: '', site_name: '', attachment_url: 'http://x/a.pdf', content: '' }),
    records: ref([]),
    selectedRecords: ref([]),
    usePaginated: false,
    parseStatusLabelKey: computed(() => 'announce.detail.parse_status.pending'),
    parseStatusSeverity: computed(() => 'secondary'),
    parseButtonLabelKey: computed(() => 'announce.detail.btn_parse'),
    parseButtonDisabled: computed(() => false),
    sanitizedContent: computed(() => ''),
    startParse: vi.fn(),
    statusLabelKey: (s: string) => `announce.detail.record_status.${s}`,
    statusSeverity: () => 'secondary',
    onCellEditComplete: vi.fn(),
    handleBatchApprove: vi.fn(),
    displayRecords: ref([]),
    isLoadingMore: ref(false),
    showLoadAllButton: ref(false),
    loadAllRemaining: vi.fn(),
    totalCount: ref(0),
    favMap: ref({}),
    favStatusMap: ref({}),
    isFavLoading: ref(false),
    toggleFavorite: vi.fn(),
  }),
}))

type Locale = 'zh-CN' | 'zh-TW' | 'en'

function makeI18n(locale: Locale = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

/** 只渲染文案的 PrimeVue stub（label/value/header 走 $attrs，插槽原样透出） */
const TEXT_STUBS = {
  Button: { template: '<button>{{ $attrs.label }}<slot /></button>', inheritAttrs: false },
  Card: { template: '<div><slot name="title" /><slot name="content" /></div>' },
  DataTable: { template: '<div><slot /></div>' },
  Column: { template: '<div>{{ $attrs.header }}</div>', inheritAttrs: false },
  Tag: { template: '<span class="tag">{{ $attrs.value }}</span>', inheritAttrs: false },
  InputText: { template: '<input :placeholder="$attrs.placeholder" />', inheritAttrs: false },
  Select: { template: '<div />' },
  Message: { template: '<div><slot /></div>' },
  ProgressSpinner: { template: '<div />' },
  AppCalendar: { template: '<div />' },
  TableLoadFooter: { template: '<div />' },
  FavoriteStatusTag: { template: '<div />' },
  UnifiedFilterBar: { template: '<div />' },
  LogBar: { template: '<div />' },
}

function mountWith(component: unknown, locale: Locale) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:all(.*)', component: { template: '<div />' } }],
  })
  return mount(component as never, {
    global: { plugins: [makeI18n(locale), ToastService, router], stubs: TEXT_STUBS },
  } as never)
}

async function expectSwitches(component: unknown, zhText: string, enText: string) {
  const zhWrapper = mountWith(component, 'zh-CN')
  await flushPromises()
  expect(zhWrapper.text(), `zh-CN 未渲染「${zhText}」`).toContain(zhText)

  const enWrapper = mountWith(component, 'en')
  await flushPromises()
  expect(enWrapper.text(), `en 未渲染「${enText}」`).toContain(enText)
}

describe('批 4 i18n：公告详情 / 标准状态文案随语言切换', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('StandardsStatusView：页面标题与筛选项随语言切换', async () => {
    const { default: StandardsStatusView } = await import('./StandardsStatusView.vue')
    await expectSwitches(StandardsStatusView, '标准状态', 'Standards Status')
  })

  it('AnnounceDetail：页面字段标签随语言切换（含 composable 返回的 key 经 t() 渲染）', async () => {
    const { default: AnnounceDetail } = await import('./AnnounceDetail.vue')
    await expectSwitches(AnnounceDetail, '批量确认入库', 'Batch Approve')
  })

  it('AnnounceDetail：composable 的 labelKey 经组件 t() 翻译，不出现 key 回显', async () => {
    const { default: AnnounceDetail } = await import('./AnnounceDetail.vue')
    const zh = mountWith(AnnounceDetail, 'zh-CN')
    await flushPromises()
    expect(zh.html()).not.toContain('announce.detail.')
    expect(zh.text()).toContain('待解析')      // parseStatusLabelKey → t()
    expect(zh.text()).toContain('开始解析')    // parseButtonLabelKey → t()

    const english = mountWith(AnnounceDetail, 'en')
    await flushPromises()
    expect(english.html()).not.toContain('announce.detail.')
    expect(english.text()).toContain('Pending')
    expect(english.text()).toContain('Start Parsing')
  })
})
