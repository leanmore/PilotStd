// api/standards.test.ts — 标准状态 API + 首屏内存 TTL 缓存（NEW-44）
//
// 缓存是本模块唯一有状态的逻辑，重点锁住：
//   · 仅 page=1/未指定 page 走缓存（page>1 增量加载页码动态变化，必须直连）；
//   · 缓存 key 区分 status/name/standard_no 三个筛选维度（不同筛选不能互相命中）；
//   · TTL 5 分钟，过期重新请求；clearStandardsStatusCache 立即失效；
//   · 失败不写缓存（下次调用重新请求）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import {
  clearStandardsStatusCache,
  getStandardsStats,
  getStandardsStatus,
} from './standards'

const PAGE = { total: 0, page: 1, page_size: 50, items: [] }

describe('standards API', () => {
  let nowSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    clearStandardsStatusCache()
    nowSpy = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
  })

  afterEach(() => {
    nowSpy.mockRestore()
  })

  it('getStandardsStats 走 GET /standards/status/stats 并透传 routeTag', async () => {
    const stats = { active: 1, inactive: 2, upcoming: 3, unknown: 0 }
    h.get.mockResolvedValueOnce({ data: stats })

    await expect(getStandardsStats('/standards-status')).resolves.toEqual(stats)
    expect(h.get).toHaveBeenCalledWith('/standards/status/stats', {
      routeTag: '/standards-status',
    })
  })

  it('首屏请求后命中 5 分钟缓存：同参数第二次不再发请求且返回同一引用', async () => {
    h.get.mockResolvedValue({ data: PAGE })

    const first = await getStandardsStatus({ status: 'active' }, '/standards-status')
    const second = await getStandardsStatus({ status: 'active' }, '/standards-status')

    expect(h.get).toHaveBeenCalledTimes(1)
    expect(h.get).toHaveBeenCalledWith('/standards/status', {
      params: { status: 'active' },
      routeTag: '/standards-status',
    })
    expect(second).toBe(first)
  })

  it('缓存 key 区分 status/name/standard_no 三个筛选维度', async () => {
    h.get.mockResolvedValue({ data: PAGE })

    await getStandardsStatus({ status: 'active' })
    await getStandardsStatus({ name: 'GB' })
    await getStandardsStatus({ standard_no: 'GB/T 1' })
    await getStandardsStatus({ status: 'inactive' })
    expect(h.get).toHaveBeenCalledTimes(4)

    // 重复第一组仍命中缓存，说明 key 没有被后几组覆盖
    await getStandardsStatus({ status: 'active' })
    expect(h.get).toHaveBeenCalledTimes(4)
  })

  it('page>1 跳过缓存（增量加载每次直连）；显式 page=1 仍走缓存', async () => {
    h.get.mockResolvedValue({ data: { ...PAGE, page: 2 } })

    await getStandardsStatus({ page: 2 })
    await getStandardsStatus({ page: 2 })
    expect(h.get).toHaveBeenCalledTimes(2)

    h.get.mockResolvedValue({ data: PAGE })
    await getStandardsStatus({ page: 1 })
    await getStandardsStatus({ page: 1 })
    expect(h.get).toHaveBeenCalledTimes(3)
  })

  it('TTL 5 分钟：未到期命中缓存，到期后重新请求', async () => {
    h.get.mockResolvedValue({ data: PAGE })

    await getStandardsStatus({})
    nowSpy.mockReturnValue(1_000_000 + 299_999)
    await getStandardsStatus({})
    expect(h.get).toHaveBeenCalledTimes(1)

    nowSpy.mockReturnValue(1_000_000 + 300_000)
    await getStandardsStatus({})
    expect(h.get).toHaveBeenCalledTimes(2)
  })

  it('clearStandardsStatusCache 立即失效（刷新按钮语义）', async () => {
    h.get.mockResolvedValue({ data: PAGE })

    await getStandardsStatus({})
    clearStandardsStatusCache()
    await getStandardsStatus({})

    expect(h.get).toHaveBeenCalledTimes(2)
  })

  it('请求失败不写缓存，下次调用重新请求', async () => {
    const err = new Error('standards 500')
    h.get.mockRejectedValueOnce(err)

    await expect(getStandardsStatus({})).rejects.toBe(err)

    h.get.mockResolvedValueOnce({ data: PAGE })
    await expect(getStandardsStatus({})).resolves.toEqual(PAGE)
    expect(h.get).toHaveBeenCalledTimes(2)
  })
})
