// views/TaskView.test.ts — 归档 items 构造字段补传回归测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import TaskView from './TaskView.vue'

const mockPostScan = vi.fn()
const mockPostQuery = vi.fn()
const mockPostDownload = vi.fn()
const mockPostNormalize = vi.fn()
const mockPostArchive = vi.fn()
const mockGetSettings = vi.fn()
const mockStopPipelineRun = vi.fn()
const mockResumePipelineRun = vi.fn()

vi.mock('@/api', () => ({
  postScan: (...args: any[]) => mockPostScan(...args),
  postQuery: (...args: any[]) => mockPostQuery(...args),
  postDownload: (...args: any[]) => mockPostDownload(...args),
  postNormalize: (...args: any[]) => mockPostNormalize(...args),
  postArchive: (...args: any[]) => mockPostArchive(...args),
  getSettings: (...args: any[]) => mockGetSettings(...args),
}))

vi.mock('@/api/tasks', () => ({
  getPipelineRun: vi.fn(),
  stopPipelineRun: (...args: any[]) => mockStopPipelineRun(...args),
  resumePipelineRun: (...args: any[]) => mockResumePipelineRun(...args),
}))

vi.mock('@/composables/useUserPreferences', () => ({
  useUserPreferences: () => ({ taskPath: ref('/inbox') }),
}))

vi.mock('@/lib/storage', () => ({
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
}))

vi.mock('@/utils/taskRestore', () => ({
  restoreResultsFromStepResults: vi.fn(() => ({})),
  resolveActiveRun: vi.fn(() => null),
}))

function makeI18n(locale: 'zh-CN' | 'en' = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
}

function mountTaskView(locale: 'zh-CN' | 'en' = 'zh-CN') {
  return shallowMount(TaskView, {
    global: {
      plugins: [makeI18n(locale)],
      stubs: {
        Button: { name: 'Button', template: '<button class="p-button" @click="$emit(\'click\')"><slot /></button>', props: ['icon', 'label', 'size', 'severity', 'loading', 'text', 'disabled'] },
        Tag: { name: 'Tag', template: '<span><slot /></span>', props: ['value', 'severity'] },
        ProgressBar: { name: 'ProgressBar', template: '<div />', props: ['value'] },
        DataView: { name: 'DataView', template: '<div />' },
        Paginator: { name: 'Paginator', template: '<div />', props: ['rows', 'totalRecords', 'first'] },
        LogBar: { name: 'LogBar', template: '<div />' },
      },
    },
  })
}

describe('TaskView 归档 items 构造', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSettings.mockResolvedValue({ storage: { scan_paths: ['/inbox'] } })
    mockPostScan.mockResolvedValue({
      run_id: 'run-1',
      total: 1,
      pdf_count: 1,
      word_count: 0,
      dup_skipped: 0,
      skipped_dirs: 0,
      files: [{
        name: 'GB 150-2011.pdf',
        full_path: '/inbox/GB 150-2011.pdf',
        size: 0,
        status: 'parsed',
        standard_number: 'GB 150-2011',
        logical_code: 'GB',
        number: 150,
        year: 2011,
        num_prefix: '',
        num_suffix: '',
        ext: '.pdf',
        language: '',
        std_name: '压力容器',
      }],
    })
    mockPostQuery.mockResolvedValue({ stats: { found: 1, downloadable: 0 }, results: [] })
    mockPostDownload.mockResolvedValue({ stats: { success: 0, skipped: 0 } })
    mockPostNormalize.mockResolvedValue({ results: [{ source_path: '/inbox/GB 150-2011.pdf', new_filename: 'GB 150-2011 压力容器.pdf' }] })
    mockPostArchive.mockResolvedValue({ ok: true })
  })

  it('归档 items 包含 logical_code 字段且值正确', async () => {
    const wrapper = mountTaskView()
    await flushPromises()

    // 触发「开始任务」按钮的 click 事件
    wrapper.findComponent({ name: 'Button' }).vm.$emit('click')
    for (let i = 0; i < 10; i++) {
      await flushPromises()
    }

    expect(mockPostArchive).toHaveBeenCalledTimes(1)
    const items = mockPostArchive.mock.calls[0][0]
    expect(items.length).toBe(1)
    expect(items[0].logical_code).toBe('GB')
    expect(items[0].num_prefix).toBe('')
  })

  it('下载成功的文件也进入归档 items', async () => {
    mockPostQuery.mockResolvedValue({
      stats: { found: 1, downloadable: 1 },
      results: [{ standard_number: 'GB 150-2011', match_status: 'exact', is_adopted: false }],
    })
    mockPostDownload.mockResolvedValue({
      stats: { success: 1, skipped: 0 },
      results: [{
        standard_number: 'GB 150-2011',
        standard_name: '压力容器',
        status: 'success',
        saved_path: '/standards/GB 150-2011 压力容器.pdf',
      }],
    })
    const wrapper = mountTaskView()
    await flushPromises()
    wrapper.findComponent({ name: 'Button' }).vm.$emit('click')
    for (let i = 0; i < 10; i++) await flushPromises()

    const items = mockPostArchive.mock.calls[0][0]
    expect(items).toHaveLength(2)
    expect(items.map((i: any) => i.source_path)).toContain('/standards/GB 150-2011 压力容器.pdf')
  })

  it('20 个 exact 项全部进入下载，不再截断为 10', async () => {
    const results = Array.from({ length: 20 }, (_, i) => ({
      standard_number: `GB/T ${i + 1}-2020`,
      match_status: 'exact',
      is_adopted: false,
    }))
    mockPostQuery.mockResolvedValue({ stats: { found: 20, downloadable: 20 }, results })
    mockPostDownload.mockResolvedValue({
      stats: { success: 20, skipped: 0 },
      results: results.map((r, i) => ({
        standard_number: r.standard_number,
        standard_name: `标准 ${i + 1}`,
        status: 'success',
        saved_path: `/standards/${i + 1}.pdf`,
      })),
    })
    const wrapper = mountTaskView()
    await flushPromises()
    wrapper.findComponent({ name: 'Button' }).vm.$emit('click')
    for (let i = 0; i < 12; i++) await flushPromises()

    expect(mockPostDownload).toHaveBeenCalledTimes(1)
    const dlNums = mockPostDownload.mock.calls[0][0]
    expect(dlNums).toHaveLength(20)
    expect(dlNums[0]).toBe('GB/T 1-2020')
    expect(dlNums[19]).toBe('GB/T 20-2020')

    const items = mockPostArchive.mock.calls[0][0]
    expect(items).toHaveLength(21) // 1 个扫描件 + 20 个下载件
    const paths = items.map((i: any) => i.source_path)
    for (let i = 1; i <= 20; i++) expect(paths).toContain(`/standards/${i}.pdf`)
  })

  it('任务页提供停止按钮', async () => {
    const wrapper = mountTaskView()
    await flushPromises()
    const buttons = wrapper.findAllComponents({ name: 'Button' })
    expect(buttons.length).toBe(2)
    expect(buttons[1].props('label')).toContain('停止')
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', async () => {
    const zh = mountTaskView('zh-CN')
    await flushPromises()
    expect(zh.text()).toContain('标准处理流水线')
    expect(zh.text()).toContain('规范化')

    const english = mountTaskView('en')
    await flushPromises()
    expect(english.text()).toContain('Standard processing pipeline')
    expect(english.text()).toContain('Normalize')
  })
})
