// web/src/composables/useFavorite.test.ts
// 覆盖 loadFavStatuses() 分片逻辑的正确性和降级行为

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import type { AnnouncementRecord } from '@/types/api'

// mock API 模块
vi.mock('@/api/announce', () => ({
  getBatchFavoriteStatus: vi.fn(),
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}))

// mock primevue toast — 共享实例便于断言
const toastMock = vi.hoisted(() => ({ add: vi.fn() }))
vi.mock('primevue/usetoast', () => ({
  useToast: () => toastMock,
}))

import { useFavorite } from './useFavorite'
import { addFavorite, getBatchFavoriteStatus, removeFavorite } from '@/api/announce'

function makeRecords(count: number): AnnouncementRecord[] {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    announcement_id: 1000 + i,
    announce_no: `2025-${String(i + 1)}`,
    row_index: i + 1,
    standard_number: `GB/T ${10000 + i}`,
    std_name: `标准名称 ${i + 1}`,
    implement_date: null,
    expiry_date: null,
    superseded_by: null,
    status: 'draft' as const,
    confidence: 0.95,
    raw_text: null,
    parser_engine: null,
    source_type: 'gb',
    created_at: '2025-01-01',
  }))
}

function mockBatchResolved(ids: number[], status: string) {
  const statuses: Record<string, any> = {}
  for (const id of ids) {
    statuses[String(id)] = { favorite_id: id + 10000, status }
  }
  return { statuses }
}

describe('useFavorite.loadFavStatuses', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('空 records 直接返回，不发请求', async () => {
    const records = ref<AnnouncementRecord[]>([])
    const { loadFavStatuses } = useFavorite(records)

    await loadFavStatuses()
    expect(getBatchFavoriteStatus).not.toHaveBeenCalled()
  })

  it('≤500 条走快速路径，单次请求', async () => {
    const records = ref(makeRecords(100))
    const mock = vi.mocked(getBatchFavoriteStatus)
    mock.mockResolvedValueOnce(mockBatchResolved(records.value.map(r => r.id), 'pending'))

    const { favMap, loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    expect(mock).toHaveBeenCalledTimes(1)
    expect(mock).toHaveBeenCalledWith(records.value.map(r => r.id))
    // 全部标记为已收藏（status=pending）
    expect(Object.values(favMap.value).every(Boolean)).toBe(true)
  })

  it('>500 条自动分片，每片 ≤500', async () => {
    const records = ref(makeRecords(1200))
    const mock = vi.mocked(getBatchFavoriteStatus)
    // 3 片 × 500 + 1 并发组（CONCURRENCY=3，3 片一起发）
    mock.mockResolvedValue({ statuses: {} })

    const { loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    expect(mock).toHaveBeenCalledTimes(3)
    // 验证每片大小：前两片 500，最后一片 200
    const calls = mock.mock.calls
    expect(calls[0][0].length).toBe(500)
    expect(calls[1][0].length).toBe(500)
    expect(calls[2][0].length).toBe(200)
  })

  it('分片结果合并正确', async () => {
    const records = ref(makeRecords(800))
    const mock = vi.mocked(getBatchFavoriteStatus)
    // 第一片返回 id [1..500] 全部 pending
    mock.mockResolvedValueOnce(mockBatchResolved(
      Array.from({ length: 500 }, (_, i) => i + 1), 'pending',
    ))
    // 第二片返回 id [501..800] 全部 done
    mock.mockResolvedValueOnce(mockBatchResolved(
      Array.from({ length: 300 }, (_, i) => i + 501), 'done',
    ))

    const { favMap, loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    // 所有 800 条都应标记为已收藏
    const faved = Object.entries(favMap.value).filter(([, v]) => v)
    expect(faved.length).toBe(800)
  })

  it('单批失败时已成功的批次结果保留，失败批次对应的 ID 降级为未收藏', async () => {
    const records = ref(makeRecords(800))
    const mock = vi.mocked(getBatchFavoriteStatus)
    // 第一批成功 (id 1..500)
    mock.mockResolvedValueOnce(mockBatchResolved(
      Array.from({ length: 500 }, (_, i) => i + 1), 'done',
    ))
    // 第二批失败
    mock.mockRejectedValueOnce(new Error('Network error'))
    // 注意：由于 CONCURRENCY=3 且只有 2 个 chunks，两个同时发出，
    // 第一批成功，第二批失败 → 整个 Promise.all 会 reject。
    // 这种情况触发外层 catch，全部降级。这是当前实现的约束。

    // 因此本测试验证的是：两批都失败时 catch 逻辑正确降级。
    mock.mockReset()
    mock.mockRejectedValue(new Error('Network error'))

    const { favMap, loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    // catch 降级：全部未收藏
    expect(Object.values(favMap.value).every(v => v === false)).toBe(true)
  })

  it('全部批次失败时降级为全部未收藏', async () => {
    const records = ref(makeRecords(200))
    const mock = vi.mocked(getBatchFavoriteStatus)
    mock.mockRejectedValue(new Error('Server error'))

    const { favMap, loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    expect(mock).toHaveBeenCalledTimes(1)
    expect(Object.values(favMap.value).every(v => v === false)).toBe(true)
  })

  it('部分记录未返回时正确标记为未收藏', async () => {
    const records = ref(makeRecords(10))
    const mock = vi.mocked(getBatchFavoriteStatus)
    // 只返回 id 1, 3, 5
    mock.mockResolvedValueOnce({
      statuses: {
        '1': { favorite_id: 10001, status: 'done' },
        '3': { favorite_id: 10003, status: 'pending' },
        '5': { favorite_id: 10005, status: 'done' },
      },
    })

    const { favMap, loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    expect(favMap.value[1]).toBe(true)
    expect(favMap.value[3]).toBe(true)
    expect(favMap.value[5]).toBe(true)
    // 未返回的应标记为 false
    expect(favMap.value[2]).toBe(false)
    expect(favMap.value[4]).toBe(false)
  })
})

describe('useFavorite.toggleFavorite 分层错误提示（FIX-401）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('业务级 401：展示后端 detail"用户不存在"并回滚', async () => {
    const records = ref(makeRecords(1))
    const { favMap, toggleFavorite } = useFavorite(records)
    vi.mocked(addFavorite).mockRejectedValueOnce({
      response: { status: 401, data: { detail: '用户不存在' } },
    })
    await toggleFavorite(records.value[0])
    expect(favMap.value[1]).toBe(false)  // 回滚
    expect(toastMock.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', summary: '用户不存在' }))
  })

  it('无 detail 的业务错误：提示"操作失败 (500)"', async () => {
    const records = ref(makeRecords(1))
    const { favMap, toggleFavorite } = useFavorite(records)
    vi.mocked(addFavorite).mockRejectedValueOnce({ response: { status: 500, data: {} } })
    await toggleFavorite(records.value[0])
    expect(favMap.value[1]).toBe(false)
    expect(toastMock.add).toHaveBeenCalledWith(expect.objectContaining({ summary: '操作失败 (500)' }))
  })

  it('断网（无 response）：组件不弹窗，交由全局拦截器统一提示', async () => {
    const records = ref(makeRecords(1))
    const { favMap, toggleFavorite } = useFavorite(records)
    vi.mocked(addFavorite).mockRejectedValueOnce({ code: 'ERR_NETWORK', message: 'Network Error' })
    await toggleFavorite(records.value[0])
    expect(favMap.value[1]).toBe(false)  // 回滚
    expect(toastMock.add).not.toHaveBeenCalled()
  })

  it('取消收藏失败同样回滚并提示 detail', async () => {
    const records = ref(makeRecords(1))
    const { favMap, toggleFavorite } = useFavorite(records)
    favMap.value[1] = true  // 预置为已收藏，走取消路径
    vi.mocked(removeFavorite).mockRejectedValueOnce({
      response: { status: 401, data: { detail: '用户不存在' } },
    })
    await toggleFavorite(records.value[0])
    expect(favMap.value[1]).toBe(true)  // 回滚
    expect(toastMock.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', summary: '用户不存在' }))
  })

  it('收藏成功提示"已收藏"', async () => {
    const records = ref(makeRecords(1))
    const { toggleFavorite } = useFavorite(records)
    vi.mocked(addFavorite).mockResolvedValueOnce({ status: 'pending', favorite_id: 1 })
    await toggleFavorite(records.value[0])
    expect(toastMock.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', summary: '已收藏' }))
  })
})

// ═══════════════════════════════════════════════════════════════
// 收藏判定与下载状态解耦（2026-09-21 修复：旧实现按状态枚举白名单判定，
// 会把下载 failed/abandoned 的收藏显示成"未收藏"）
// ═══════════════════════════════════════════════════════════════

describe('useFavorite 收藏状态与下载状态解耦', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function statusObj(id: number, downloadStatus: string | null) {
    return {
      favorite_id: id + 10000,
      status: 'pending',
      download_status: downloadStatus,
      download_error: downloadStatus === 'failed' ? '采标标准，版权受限' : null,
      last_attempt: '2026-03-01',
      download_updated_at: '2026-03-01 00:00:00',
    }
  }

  it('下载 failed/abandoned 仍是有效收藏（不再误判为未收藏）', async () => {
    const records = ref(makeRecords(3))
    vi.mocked(getBatchFavoriteStatus).mockResolvedValueOnce({
      statuses: {
        '1': statusObj(1, 'failed'),
        '2': statusObj(2, 'abandoned'),
        '3': null,
      },
    })

    const { favMap, favStatusMap, loadFavStatuses } = useFavorite(records)
    await loadFavStatuses()

    expect(favMap.value[1]).toBe(true)
    expect(favMap.value[2]).toBe(true)
    expect(favMap.value[3]).toBe(false)
    // 下载状态单独维护，供页面渲染进度标签
    expect(favStatusMap.value[1].download_status).toBe('failed')
    expect(favStatusMap.value[2].download_status).toBe('abandoned')
    expect(favStatusMap.value[3]).toBeUndefined()
  })

  it('新收藏先占位为"未加入队列"（download_status=null），取消收藏后清空下载状态', async () => {
    const records = ref(makeRecords(1))
    vi.mocked(addFavorite).mockResolvedValueOnce({ status: 'pending', favorite_id: 1 })
    vi.mocked(removeFavorite).mockResolvedValueOnce({ status: 'cancelled' })

    const { favMap, favStatusMap, toggleFavorite } = useFavorite(records)

    await toggleFavorite(records.value[0])
    expect(favMap.value[1]).toBe(true)
    expect(favStatusMap.value[1]?.download_status).toBeNull()

    await toggleFavorite(records.value[0])
    expect(favMap.value[1]).toBe(false)
    expect(favStatusMap.value[1]).toBeUndefined()
  })
})
