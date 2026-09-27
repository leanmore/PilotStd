// views/TaskDomainI18n.test.ts — 批 3 i18n 守卫：任务/下载/整理域文案随语言切换
//
// 覆盖 4 个**原本没有测试文件**的组件（TaskManager / DownloadImport / OrganizeView / PendingView），
// 与 TaskView / QualityView / SchedulerStatus / DownloadQueue 的切换用例合起来覆盖批 3 的 8 个文件。
// 做法同批 2：用**真实 locale 文件**挂载，空 messages 会让 t() 回显 key，因此断言能证明文案真的走 i18n。
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

vi.mock('@/api', () => ({
  getPendingItems: vi.fn().mockResolvedValue({ items: [] }),
  postRequery: vi.fn().mockResolvedValue({ results: [] }),
  getFiles: vi.fn().mockResolvedValue({ files: [] }),
  postCleanEmpty: vi.fn().mockResolvedValue({ removed: 0 }),
}))
vi.mock('@/api/validity', () => ({ enqueueValidityCheck: vi.fn().mockResolvedValue({ enqueued: 0, total: 0 }) }))
vi.mock('@/api/download', () => ({ postDownloadImport: vi.fn().mockResolvedValue({ valid: [], invalid: [], duplicates: [], results: [] }) }))
vi.mock('@/api/http', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }), put: vi.fn(), post: vi.fn() },
}))
vi.mock('@/composables/useQueryAdapters', () => ({
  useQueryAdapters: () => ({ adapters: [], loading: false, error: '', ensure: vi.fn(), refresh: vi.fn() }),
}))

type Locale = 'zh-CN' | 'zh-TW' | 'en'

function makeI18n(locale: Locale = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

/** 只渲染文案的 PrimeVue stub（label/value/header 走 $attrs，插槽原样透出） */
const TEXT_STUBS = {
  Button: { template: '<button>{{ $attrs.label }}<slot /></button>', inheritAttrs: false },
  Card: { template: '<div><slot name="content" /><slot name="title" /></div>' },
  DataTable: { template: '<div><slot /></div>' },
  Column: { template: '<div>{{ $attrs.header }}</div>', inheritAttrs: false },
  Tag: { template: '<span class="tag">{{ $attrs.value }}<slot /></span>', inheritAttrs: false },
  Textarea: { template: '<textarea :placeholder="$attrs.placeholder" />', inheritAttrs: false },
  Dialog: { template: '<div>{{ $attrs.header }}<slot /></div>', inheritAttrs: false },
  Select: { template: '<div />' },
  SelectButton: { template: '<div />' },
  ProgressBar: { template: '<div />' },
  ProgressSpinner: { template: '<div />' },
  DataView: { template: '<div><slot name="list" :items="[]" /></div>' },
  Paginator: { template: '<div />' },
  Checkbox: { template: '<input type="checkbox" />' },
  LogBar: { template: '<div />' },
  InputText: { template: '<input />' },
  InputNumber: { template: '<input type="number" />' },
  Divider: { template: '<div />' },
  Message: { template: '<div><slot /></div>' },
}

function mountWith(component: unknown, locale: Locale) {
  return mount(component as never, {
    global: { plugins: [makeI18n(locale)], stubs: TEXT_STUBS },
  } as never)
}

/** 断言「zh-CN 与 en 的可见文案都命中」——即该文案确实来自 locales */
async function expectSwitches(component: unknown, zhText: string, enText: string) {
  const zhWrapper = mountWith(component, 'zh-CN')
  await flushPromises()
  expect(zhWrapper.text(), `zh-CN 未渲染「${zhText}」`).toContain(zhText)

  const enWrapper = mountWith(component, 'en')
  await flushPromises()
  expect(enWrapper.text(), `en 未渲染「${enText}」`).toContain(enText)
}

describe('批 3 i18n：任务/下载/整理域文案随语言切换', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('TaskManager：后台任务文案随语言切换', async () => {
    const { default: TaskManager } = await import('@/components/TaskManager.vue')
    await expectSwitches(TaskManager, '后台任务', 'Background Tasks')
  })

  it('DownloadImport：手动导入下载列表文案随语言切换', async () => {
    const { default: DownloadImport } = await import('./DownloadImport.vue')
    await expectSwitches(DownloadImport, '手动导入下载列表', 'Manual Download Import')
  })

  it('OrganizeView：文件管理文案随语言切换', async () => {
    const { default: OrganizeView } = await import('./OrganizeView.vue')
    await expectSwitches(OrganizeView, '文件管理', 'File Management')
  })

  it('PendingView：待确认文案随语言切换', async () => {
    const { default: PendingView } = await import('./PendingView.vue')
    await expectSwitches(PendingView, '待确认', 'Pending')
  })
})
