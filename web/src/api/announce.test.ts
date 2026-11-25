// api/announce.test.ts — 公告抓取 / 详情 / 记录 / 收藏 API 组装逻辑（NEW-44）
//
// 只测本模块自己的契约：路径、query 与 body 的分工、可选参数缺省形状、返回值取
// 响应体 .data、失败原样透传。http 层由 http.test.ts 覆盖，这里整体 mock。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
vi.mock('./http', () => ({ default: h }))
import {
  addFavorite, batchApprove, getAnnounceDetailLite, getAnnounceFetchFailures, getAnnounceRecords,
  getAnnounceResults, getAnnouncementByNo, getAnnouncementDetail, getBatchFavoriteStatus,
  getParseStatus, listFavorites, postAnnounceCheck, removeFavorite, triggerParse, updateRecord,
} from './announce'
describe('announce API', () => {
  beforeEach(() => vi.clearAllMocks())
  it('getAnnounceResults 默认筛选为空串/分页 1-50；自定义参数与 routeTag 透传', async () => {
    const payload = { total: 0, items: [] }
    h.get.mockResolvedValue({ data: payload })

    await expect(getAnnounceResults()).resolves.toEqual(payload)
    expect(h.get).toHaveBeenLastCalledWith('/announce/results', {
      params: { source_site: '', from_date: '', page: 1, page_size: 50 },
      routeTag: undefined,
    })

    await getAnnounceResults('std.gov', '2026-01-01', '/announce', 3, 20)
    expect(h.get).toHaveBeenLastCalledWith('/announce/results', {
      params: { source_site: 'std.gov', from_date: '2026-01-01', page: 3, page_size: 20 },
      routeTag: '/announce',
    })
  })

  it('postAnnounceCheck 无参时空 query + null body；缺省筛选不得进 query', async () => {
    h.post.mockResolvedValue({ data: { ok: true } })

    await postAnnounceCheck()
    expect(h.post).toHaveBeenLastCalledWith('/announce/check', null, { params: {} })

    await postAnnounceCheck('2026-01-01')
    expect(h.post).toHaveBeenLastCalledWith('/announce/check', null, {
      params: { since_date: '2026-01-01' },
    })

    await postAnnounceCheck(undefined, 'gb,hb')
    expect(h.post).toHaveBeenLastCalledWith('/announce/check', null, { params: { types: 'gb,hb' } })
  })

  it('getAnnounceFetchFailures 默认 limit=20、只看未解决，routeTag 固定 /announce', async () => {
    const payload = { total: 0, unresolved: 0, items: [] }
    h.get.mockResolvedValue({ data: payload })

    await expect(getAnnounceFetchFailures()).resolves.toEqual(payload)
    expect(h.get).toHaveBeenLastCalledWith('/announce/fetch-failures', {
      params: { limit: 20, unresolved_only: true },
      routeTag: '/announce',
    })

    await getAnnounceFetchFailures(5, false)
    expect(h.get).toHaveBeenLastCalledWith('/announce/fetch-failures', {
      params: { limit: 5, unresolved_only: false },
      routeTag: '/announce',
    })
  })

  it('公告号 URL 编码；by-no / detail 的 source 缺省时 params 为空对象', async () => {
    h.get.mockResolvedValue({ data: {} })
    const no = 'GB/T 1-2020'
    const path = `/announcements/${encodeURIComponent(no)}`

    await getAnnouncementByNo(no, '/announce')
    expect(h.get).toHaveBeenLastCalledWith(`/announcements/by-no/${encodeURIComponent(no)}`, {
      routeTag: '/announce',
    })

    await getAnnouncementDetail(no)
    expect(h.get).toHaveBeenLastCalledWith(path, { params: {} })

    await getAnnouncementDetail(no, 'std.gov')
    expect(h.get).toHaveBeenLastCalledWith(path, { params: { source: 'std.gov' } })
  })

  it('lite / records / parse 的路径与 params：source 缺省时不出现，routeTag 透传', async () => {
    h.get.mockResolvedValue({ data: {} })
    h.post.mockResolvedValue({ data: { status: 'queued' } })
    const recordsPath = `/announcements/${encodeURIComponent('GB1')}/records`

    await getAnnounceDetailLite('GB1', 'std.gov', '/announce')
    expect(h.get).toHaveBeenLastCalledWith(`/announcements/${encodeURIComponent('GB1')}/lite`, {
      params: { source: 'std.gov' },
      routeTag: '/announce',
    })

    await getAnnounceRecords('GB1', 2, 25)
    expect(h.get).toHaveBeenLastCalledWith(recordsPath, { params: { page: 2, page_size: 25 } })

    await getAnnounceRecords('GB1', 1, 10, 'std.gov')
    expect(h.get).toHaveBeenLastCalledWith(recordsPath, {
      params: { page: 1, page_size: 10, source: 'std.gov' },
    })

    await triggerParse('GB1')
    expect(h.post).toHaveBeenLastCalledWith('/announcements/GB1/parse', null, { params: {} })

    await getParseStatus('GB1', 'std.gov')
    expect(h.get).toHaveBeenLastCalledWith('/announcements/GB1/parse-status', {
      params: { source: 'std.gov' },
    })
  })

  it('updateRecord 走 PATCH /announcement-record/:id；batchApprove 批量提交 ids', async () => {
    h.patch.mockResolvedValueOnce({ data: { status: 'ok' } })
    h.post.mockResolvedValueOnce({ data: { approved_count: 2 } })

    const updated = await updateRecord(7, { standard_number: 'GB/T 2-2020' })
    expect(h.patch).toHaveBeenCalledWith('/announcement-record/7', {
      standard_number: 'GB/T 2-2020',
    })
    expect(updated).toEqual({ status: 'ok' })

    await batchApprove([1, 2])
    expect(h.post).toHaveBeenCalledWith('/announcement-record/batch-approve', { ids: [1, 2] })
  })

  it('收藏增删/批量状态/列表：body 字段名与路径固定，params 无参为 undefined', async () => {
    h.post.mockResolvedValue({ data: { status: 'ok' } })
    h.delete.mockResolvedValue({ data: { status: 'ok' } })
    h.get.mockResolvedValue({ data: { favorites: [] } })

    await addFavorite(11)
    expect(h.post).toHaveBeenLastCalledWith('/favorites', { record_id: 11 })

    await getBatchFavoriteStatus([11, 12])
    expect(h.post).toHaveBeenLastCalledWith('/favorites/batch-status', { record_ids: [11, 12] })

    await removeFavorite(11)
    expect(h.delete).toHaveBeenCalledWith('/favorites/11')

    await listFavorites()
    expect(h.get).toHaveBeenLastCalledWith('/favorites', { params: undefined })
    await listFavorites({ status: 'active' })
    expect(h.get).toHaveBeenLastCalledWith('/favorites', { params: { status: 'active' } })
  })

  it('请求失败原样抛出（不吞错、不伪造成功）', async () => {
    const err = new Error('announce 500')
    h.post.mockRejectedValueOnce(err)

    await expect(batchApprove([1])).rejects.toBe(err)
  })
})
