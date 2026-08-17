// views/TaskView.test.ts — 归档 items 构造字段补传回归测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import TaskView from './TaskView.vue'

const mockPostScan = vi.fn()
const mockPostQuery = vi.fn()
const mockPostDownload = vi.fn()
const mockPostNormalize = vi.fn()
const mockPostArchive = vi.fn()
const mockGetSettings = vi.fn()

vi.mock('@/api', () => ({
  postScan: (...args: any[]) => mockPostScan(...args),
  postQuery: (...args: any[]) => mockPostQuery(...args),
  postDownload: (...args: any[]) => mockPostDownload(...args),
  postNormalize: (...args: any[]) => mockPostNormalize(...args),
  postArchive: (...args: any[]) => mockPostArchive(...args),
  getSettings: (...args: any[]) => mockGetSettings(...args),
}))

vi.mock('@/api/tasks', () => ({ getPipelineRun: vi.fn() }))

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

function mountTaskView() {
  return shallowMount(TaskView, {
    global: {
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
})
