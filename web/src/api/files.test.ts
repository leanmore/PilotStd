// files.test.ts — 文件浏览 / 扫描 / 整理 / 归档 / 清理 / 上传 API 组装逻辑（NEW-44）
//
// 重点锁住容易回归的组装细节：
//   - query 参数与 body 的分工（/scan 的 path 在 query、run_id 在 body）；
//   - 布尔参数显式转字符串（避免 axios 对 undefined/boolean 的序列化差异）；
//   - 可选参数缺省时的字段形状（undefined / null，后端按“无值”处理）；
//   - 上传使用 FormData 且字段名固定为 file；
//   - 返回 .data 与失败透传。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('./http', () => ({ default: h }))

import {
  getFiles,
  postArchive,
  postCleanEmpty,
  postNormalize,
  postScan,
  uploadFile,
} from './files'

const items = [
  { source_path: 'D:/raw/a.pdf', new_filename: 'GB1-2020.pdf' },
]

describe('files API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getFiles 走 GET /files，path 放 params、routeTag 透传', async () => {
    h.get.mockResolvedValueOnce({ data: { path: '/data', files: [] } })

    const result = await getFiles('/data', '/organize')

    expect(h.get).toHaveBeenCalledWith('/files', {
      params: { path: '/data' },
      routeTag: '/organize',
    })
    // 空目录是合法边界，必须原样返回而不是报错
    expect(result).toEqual({ path: '/data', files: [] })

    h.get.mockResolvedValueOnce({ data: { path: '/data', files: [] } })
    await getFiles('/data')
    expect(h.get).toHaveBeenLastCalledWith('/files', {
      params: { path: '/data' },
      routeTag: undefined,
    })
  })

  it('postScan 默认递归：path 在 query、recursive 转字符串、run_id 缺省为 null', async () => {
    const scan = { run_id: 'srv-1', total: 0, pdf_count: 0, word_count: 0, dup_skipped: 0, skipped_dirs: 0, files: [] }
    h.post.mockResolvedValueOnce({ data: scan })

    const result = await postScan('/data')

    expect(h.post).toHaveBeenCalledWith(
      '/scan',
      { run_id: null },
      { params: { path: '/data', recursive: 'true' } },
    )
    expect(result).toEqual(scan)
  })

  it('postScan 显式非递归 + runId：recursive 为 "false"、run_id 写入 body', async () => {
    h.post.mockResolvedValueOnce({ data: { run_id: 'run-9', files: [] } })

    await postScan('/data', false, 'run-9')

    expect(h.post).toHaveBeenCalledWith(
      '/scan',
      { run_id: 'run-9' },
      { params: { path: '/data', recursive: 'false' } },
    )
  })

  it('postScan 空字符串 runId 视为无值（落回 null）', async () => {
    h.post.mockResolvedValueOnce({ data: { run_id: '', files: [] } })

    await postScan('/data', true, '')

    expect(h.post.mock.calls[0][1]).toEqual({ run_id: null })
  })

  it('postNormalize 走 POST /normalize，items 与 run_id 一起提交', async () => {
    const response = { results: items }
    h.post.mockResolvedValueOnce({ data: response })

    const result = await postNormalize(items, 'run-1')

    expect(h.post).toHaveBeenCalledWith('/normalize', { items, run_id: 'run-1' })
    expect(result).toEqual(response)
  })

  it('postArchive 缺省可选参数时字段仍存在且为 undefined', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true } })

    await postArchive(items)

    expect(h.post).toHaveBeenCalledWith('/archive', {
      items,
      word_source_root: undefined,
      run_id: undefined,
    })
  })

  it('postArchive 传入 word_source_root 与 runId 时完整透传', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true } })

    await postArchive(items, 'D:/word', 'run-2')

    expect(h.post).toHaveBeenCalledWith('/archive', {
      items,
      word_source_root: 'D:/word',
      run_id: 'run-2',
    })
  })

  it('postCleanEmpty 走 POST /clean-empty：空 body + path 在 params', async () => {
    const cleaned = { cleaned: 3, removed: 1 }
    h.post.mockResolvedValueOnce({ data: cleaned })

    const result = await postCleanEmpty('/data/empty')

    expect(h.post).toHaveBeenCalledWith('/clean-empty', null, { params: { path: '/data/empty' } })
    expect(result).toEqual(cleaned)
  })

  it('uploadFile 用 FormData 且字段名固定为 file，返回后端 url', async () => {
    h.post.mockResolvedValueOnce({ data: { url: '/api/download/a.pdf', filename: 'a.pdf' } })
    const file = new File(['pdf-bytes'], 'a.pdf', { type: 'application/pdf' })

    const result = await uploadFile(file)

    expect(h.post).toHaveBeenCalledTimes(1)
    expect(h.post.mock.calls[0][0]).toBe('/upload')
    const fd = h.post.mock.calls[0][1] as FormData
    expect(fd).toBeInstanceOf(FormData)
    // 后端按字段名 file 取文件，多/少字段都会 400
    expect(fd.getAll('file')).toHaveLength(1)
    expect((fd.get('file') as File).name).toBe('a.pdf')
    expect(result).toEqual({ url: '/api/download/a.pdf', filename: 'a.pdf' })
  })

  it('请求失败时原样抛出（不吞错）', async () => {
    const err = new Error('scan failed')
    h.post.mockRejectedValueOnce(err)

    await expect(postScan('/data')).rejects.toBe(err)
  })
})
