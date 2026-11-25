// api/download.test.ts — 标准文件下载 / 手动导入（NEW-44）
//
// 两个函数的返回契约**故意不同**，最容易被“顺手统一”改坏：
//   · postDownload 取响应体 .data（调用方只关心解析结果）；
//   · postDownloadImport 返回**完整 AxiosResponse**（导入页要读 status）；
//   · 导入用 FormData 且字段名固定 'text'（后端按该字段取文本，改名字即 400）。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import { postDownload, postDownloadImport } from './download'

describe('download API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('postDownload 走 POST /download，numbers 与 run_id 一起提交，返回 .data', async () => {
    const payload = { results: [{ standard_number: 'GB/T 1-2020', status: 'ok' }] }
    h.post.mockResolvedValueOnce({ data: payload })

    const result = await postDownload(['GB/T 1-2020'], 'run-1')

    expect(h.post).toHaveBeenCalledWith('/download', {
      numbers: ['GB/T 1-2020'],
      run_id: 'run-1',
    })
    expect(result).toEqual(payload)
  })

  it('postDownload 缺省 runId 时字段保留为 undefined（后端按无运行上下文处理）', async () => {
    h.post.mockResolvedValueOnce({ data: { results: [] } })

    await postDownload([])

    expect(h.post.mock.calls[0][1]).toEqual({ numbers: [], run_id: undefined })
  })

  it('postDownloadImport 用 FormData 字段 text 提交原文，返回完整 AxiosResponse', async () => {
    const response = { status: 200, data: { valid: [], invalid: [], duplicates: [], total: 0 } }
    h.post.mockResolvedValueOnce(response)

    const result = await postDownloadImport('GB/T 1-2020\nGB/T 2-2020')

    expect(h.post).toHaveBeenCalledTimes(1)
    expect(h.post.mock.calls[0][0]).toBe('/download/import')
    const fd = h.post.mock.calls[0][1] as FormData
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('text')).toBe('GB/T 1-2020\nGB/T 2-2020')
    expect(result).toBe(response)
  })

  it('失败原样透传（不吞错）', async () => {
    const err = new Error('import failed')
    h.post.mockRejectedValueOnce(err)

    await expect(postDownloadImport('x')).rejects.toBe(err)
  })
})
