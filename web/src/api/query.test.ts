// query.test.ts — 查询 / 待确认 API 组装逻辑（NEW-44）
//
// 重点契约：
//   - /query 的 numbers 在 body、forceRefresh 在 query（且仅在 true 时出现）；
//   - /query/save 直接把 results 数组作为 body（不额外包一层）；
//   - getQueryResults 是唯一返回完整 AxiosResponse 的函数（不取 .data），
//     调用方依赖 status/headers，不能“顺手”改成取 data；
//   - /pending/requery 的 body 是裸数组、site 在 query；
//   - 失败透传。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('./http', () => ({ default: h }))

import {
  getPendingItems,
  getQueryResults,
  postQuery,
  postRequery,
  saveQueryResults,
} from './query'

const results = [
  {
    standard_number: 'GB/T 1-2020',
    standard_name: '示例标准',
    status: '现行',
    status_key: 'active',
    replaces: '',
    implementation_date: '2020-01-01',
    responsible_dept: '',
    is_adopted: false,
    match_status: 'exact',
    source_site: 'std.gov',
    publish_date: '',
    abolition_date: '',
    hcno: '',
    split_into: '',
    is_downloadable: true,
    error_message: '',
  },
]

describe('query API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('postQuery 默认不强制刷新：numbers 在 body、query params 为空对象', async () => {
    const payload = { stats: { found: 1, downloadable: 1 }, results }
    h.post.mockResolvedValueOnce({ data: payload })

    const result = await postQuery(['GB/T 1-2020'])

    expect(h.post).toHaveBeenCalledWith(
      '/query',
      { numbers: ['GB/T 1-2020'], run_id: undefined },
      { params: {} },
    )
    expect(result).toEqual(payload)
  })

  it('postQuery 强制刷新时仅追加 force_refresh=true，并透传 runId', async () => {
    h.post.mockResolvedValueOnce({ data: { stats: { found: 0, downloadable: 0 }, results: [] } })

    await postQuery(['GB/T 1-2020'], true, 'run-7')

    expect(h.post).toHaveBeenCalledWith(
      '/query',
      { numbers: ['GB/T 1-2020'], run_id: 'run-7' },
      { params: { force_refresh: true } },
    )
  })

  it('postQuery 空号码列表也照常发出（由后端决定结果）', async () => {
    h.post.mockResolvedValueOnce({ data: { stats: { found: 0, downloadable: 0 }, results: [] } })

    await postQuery([])

    expect(h.post.mock.calls[0][1]).toEqual({ numbers: [], run_id: undefined })
  })

  it('saveQueryResults 把 results 数组原样作为 body，返回保存计数', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true, count: 1 } })

    const result = await saveQueryResults(results)

    // 直接传数组，不能再包 { results } —— 后端契约
    expect(h.post).toHaveBeenCalledTimes(1)
    expect(h.post.mock.calls[0][0]).toBe('/query/save')
    expect(h.post.mock.calls[0][1]).toBe(results)
    expect(result).toEqual({ ok: true, count: 1 })
  })

  it('getQueryResults 返回完整 AxiosResponse（不取 .data），并透传 options', async () => {
    const response = { status: 200, data: { results } }
    h.get.mockResolvedValueOnce(response)

    const plain = await getQueryResults()
    expect(h.get).toHaveBeenLastCalledWith('/query/results', undefined)
    expect(plain).toBe(response)

    h.get.mockResolvedValueOnce(response)
    const tagged = await getQueryResults({ routeTag: '/' })
    expect(h.get).toHaveBeenLastCalledWith('/query/results', { routeTag: '/' })
    expect(tagged).toBe(response)
  })

  it('getPendingItems 走 GET /pending，空列表是合法边界', async () => {
    h.get.mockResolvedValueOnce({ data: { items: [] } })

    const result = await getPendingItems()

    expect(h.get).toHaveBeenCalledWith('/pending')
    expect(result).toEqual({ items: [] })
  })

  it('postRequery body 为裸数组：无 site 时 params 为空对象', async () => {
    h.post.mockResolvedValueOnce({ data: { results: [] } })

    await postRequery(['GB/T 1-2020'])

    expect(h.post).toHaveBeenCalledWith('/pending/requery', ['GB/T 1-2020'], { params: {} })
  })

  it('postRequery 传 site 时放进 query params', async () => {
    h.post.mockResolvedValueOnce({ data: { results } })

    const result = await postRequery(['GB/T 1-2020'], 'std.gov')

    expect(h.post).toHaveBeenCalledWith('/pending/requery', ['GB/T 1-2020'], {
      params: { site: 'std.gov' },
    })
    expect(result.results).toEqual(results)
  })

  it('请求失败时原样抛出（不吞错）', async () => {
    const err = new Error('query timeout')
    h.post.mockRejectedValueOnce(err)

    await expect(postQuery(['GB/T 1-2020'])).rejects.toBe(err)
  })
})
