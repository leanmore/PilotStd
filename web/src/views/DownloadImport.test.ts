// DownloadImport 测试（Q24 手动导入下载列表）
//
// 契约：文本域一行一个标准号；空输入时提交按钮禁用；提交后按 valid/invalid/duplicates
// 统计并渲染下载结果；无效条目可展开/收起；清空按钮同时清输入与结果；上传文件把内容追加到文本域。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { postDownloadImport } from '@/api/download'
import DownloadImport from './DownloadImport.vue'

vi.mock('@/api/download', () => ({ postDownloadImport: vi.fn() }))

type ImportResult = {
  valid: string[]; invalid: string[]; duplicates: string[]; total: number
  success: number; failed: number; skipped: number
  results: Array<{ standard_number: string; standard_name: string; status: string; saved_path: string; error: string }>
}

function makeResult(over: Partial<ImportResult> = {}): ImportResult {
  return {
    valid: ['GB/T 1', 'ISO 9001'], invalid: ['BAD-1'], duplicates: ['GB/T 1'],
    total: 4, success: 2, failed: 0, skipped: 0,
    results: [{ standard_number: 'GB/T 1', standard_name: '标准一', status: 'success', saved_path: '/s/1.pdf', error: '' }],
    ...over,
  }
}

function mountView() {
  return mount(DownloadImport, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { AppTable: true, Column: true },
    },
  })
}

function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('DownloadImport 手动导入', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(postDownloadImport).mockResolvedValue({ data: makeResult() } as never)
  })

  it('初始状态：提交按钮禁用、无结果区', async () => {
    const wrapper = mountView()
    expect(wrapper.text()).toContain('手动导入下载列表')
    expect(button(wrapper, '提交下载')!.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.result-area').exists()).toBe(false)
  })

  it('提交时把文本域原文传给 postDownloadImport，并渲染三档统计', async () => {
    const wrapper = mountView()
    await wrapper.find('textarea').setValue('GB/T 1\nISO 9001')
    await button(wrapper, '提交下载')!.trigger('click')
    await flushPromises()

    expect(postDownloadImport).toHaveBeenCalledWith('GB/T 1\nISO 9001')
    expect(wrapper.find('.result-area').exists()).toBe(true)
    const text = wrapper.text()
    expect(text).toContain('有效')
    expect(text).toContain('无效')
    expect(text).toContain('重复')
    expect(text).toContain('下载结果')
  })

  it('无效条目默认收起，点击后展开列表再收起', async () => {
    const wrapper = mountView()
    await wrapper.find('textarea').setValue('GB/T 1')
    await button(wrapper, '提交下载')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('查看无效条目 (1)')
    expect(wrapper.text()).not.toContain('BAD-1')
    await button(wrapper, '查看无效条目')!.trigger('click')
    expect(wrapper.text()).toContain('BAD-1')
    expect(wrapper.text()).toContain('收起无效条目')
    await button(wrapper, '收起无效条目')!.trigger('click')
    expect(wrapper.text()).not.toContain('BAD-1')
  })

  it('无下载明细（results 为空）时不渲染结果表格标题', async () => {
    vi.mocked(postDownloadImport).mockResolvedValue({ data: makeResult({ results: [] }) } as never)
    const wrapper = mountView()
    await wrapper.find('textarea').setValue('GB/T 1')
    await button(wrapper, '提交下载')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('下载结果')
  })

  it('清空按钮同时清空输入与结果', async () => {
    const wrapper = mountView()
    await wrapper.find('textarea').setValue('GB/T 1')
    await button(wrapper, '提交下载')!.trigger('click')
    await flushPromises()
    await button(wrapper, '清空')!.trigger('click')

    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('')
    expect(wrapper.find('.result-area').exists()).toBe(false)
  })

  it('接口失败只清空结果，不抛异常（提交按钮恢复可用）', async () => {
    vi.mocked(postDownloadImport).mockRejectedValue(new Error('500'))
    const wrapper = mountView()
    await wrapper.find('textarea').setValue('GB/T 1')
    await button(wrapper, '提交下载')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.result-area').exists()).toBe(false)
    expect(button(wrapper, '提交下载')!.attributes('disabled')).toBeUndefined()
  })

  it('上传 CSV/TXT：按行 trim、去空行后追加到文本域', async () => {
    class FakeFileReader {
      // 借用 lib 的 onload 签名（参数名不落进本文件，避免 no-unused-vars 误报）
      onload: FileReader['onload'] = null
      readAsText() {
        this.onload?.({ target: { result: 'GB/T 2\n\n  ISO 9001  \n' } } as ProgressEvent<FileReader>)
      }
    }
    vi.stubGlobal('FileReader', FakeFileReader)
    const wrapper = mountView()
    const vm = wrapper.vm as unknown as { handleFileUpload: () => void }
    const input = { files: [new File(['x'], 'list.txt')], value: 'C:/list.txt' }
    vm.handleFileUpload({ target: input } as unknown as Event)
    await flushPromises()

    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('GB/T 2\nISO 9001')
    expect(input.value).toBe('')
  })

  it('提交失败：展示错误提示，不静默（D-8 回归）', async () => {
    vi.mocked(postDownloadImport).mockRejectedValue({ response: { data: { detail: '文件格式不支持' } } })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('textarea').setValue('GB/T 1-2020')
    await wrapper.findAll('button').find((b) => b.text().includes('提交'))!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('文件格式不支持')
  })
})
