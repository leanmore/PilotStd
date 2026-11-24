// web/src/composables/useQueryAdapters.test.ts — 查询适配器列表 composable 单元测试
//
// NEW-44 补齐：此前 `useQueryAdapters.ts` 无任何测试。本文件锁定**对外行为**：
//   1. 首次 / 缓存过期才拉取，TTL（5 分钟）内命中模块级缓存（含 300s 边界）
//   2. 脏数据过滤（缺 `name` / `display_name` 的条目丢弃，且开发者日志可观测）
//   3. 失败路径：error 可观测、旧数据不被清空；成功刷新后 error 清除
//   4. `invalidateCache()` 打破缓存、`routeTag` 透传给 http
//   5. loading/error 是**模块级单例**（PendingView 等多调用方共享同一份）
//
// 全部依赖 mock（`@/api/http`），不联网；i18n 用真实全局实例以顺带校验
// `query_adapters.load_failed` 键确实存在于 locale，而不是吞错返回空串。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { RouteTag } from '@/types/route-tag'

const httpMock = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('@/api/http', () => ({ default: { get: httpMock.get } }))

import { useQueryAdapters } from './useQueryAdapters'
import { i18n } from '@/i18n'

/** 与源码 DEFAULT_TTL 对齐的缓存时长 */
const TTL_MS = 300_000
const LOAD_FAILED_TEXT = i18n.global.t('query_adapters.load_failed') as string

const VALID = [
  { name: 'gb', display_name: '国家标准' },
  { name: 'hb', display_name: '行业标准' },
]

function resolveAdapters(adapters: unknown) {
  httpMock.get.mockResolvedValue({ data: { adapters } })
}

describe('useQueryAdapters', () => {
  beforeEach(async () => {
    httpMock.get.mockReset()
    // loading/error 是模块级共享 ref，会跨用例残留；先用一次成功刷新复位到干净状态
    resolveAdapters([])
    const probe = useQueryAdapters()
    await probe.refresh()
    probe.invalidateCache()
    httpMock.get.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  // ── 初始状态 ──────────────────────────────────────────────────────
  it('无缓存时初始 adapters 为空、loading=false、error=null', () => {
    const { adapters, loading, error } = useQueryAdapters()

    expect(adapters.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(httpMock.get).not.toHaveBeenCalled()
  })

  // ── 成功路径 ──────────────────────────────────────────────────────
  it('refresh 成功：请求 /adapter/status 并写入 adapters，结束时清空 loading/error', async () => {
    resolveAdapters(VALID)
    const { adapters, loading, error, refresh } = useQueryAdapters()

    await refresh()

    expect(httpMock.get).toHaveBeenCalledTimes(1)
    expect(httpMock.get).toHaveBeenCalledWith('/adapter/status', {
      params: { type: 'query' },
      routeTag: undefined,
    })
    expect(adapters.value).toEqual(VALID)
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('过滤脏数据：缺 name 或 display_name 的条目丢弃并写开发者日志', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    resolveAdapters([
      { name: 'gb', display_name: '国家标准' },
      { name: '', display_name: '缺 name' },
      { name: 'hb', display_name: '' },
      { name: 'db', display_name: '地方标准' },
    ])
    const { adapters, refresh } = useQueryAdapters()

    await refresh()

    expect(adapters.value).toEqual([
      { name: 'gb', display_name: '国家标准' },
      { name: 'db', display_name: '地方标准' },
    ])
    expect(warn).toHaveBeenCalledTimes(2)
  })

  it('后端未返回 adapters / data 时回落为空数组（不抛错）', async () => {
    const { adapters, error, refresh } = useQueryAdapters()

    httpMock.get.mockResolvedValueOnce({ data: {} })
    await refresh()
    expect(adapters.value).toEqual([])
    expect(error.value).toBeNull()

    httpMock.get.mockResolvedValueOnce({ data: null })
    await refresh()
    expect(adapters.value).toEqual([])
    expect(error.value).toBeNull()
  })

  it('TTL 内（含恰好 300s 边界）命中缓存，超过 1ms 才重新拉取', async () => {
    vi.useFakeTimers()
    resolveAdapters(VALID)
    const { refresh, ensure } = useQueryAdapters()

    // 在 fake 时钟下建立 lastFetch 基准，使边界断言不受真实耗时干扰
    await refresh()
    expect(httpMock.get).toHaveBeenCalledTimes(1)

    // 恰好 300_000ms：`Date.now() - lastFetch > TTL` 为 false ⇒ 仍命中
    vi.advanceTimersByTime(TTL_MS)
    await ensure()
    expect(httpMock.get).toHaveBeenCalledTimes(1)

    // 再过 1ms：过期 ⇒ 重新请求
    vi.advanceTimersByTime(1)
    await ensure()
    expect(httpMock.get).toHaveBeenCalledTimes(2)
    expect(httpMock.get).toHaveBeenLastCalledWith('/adapter/status', {
      params: { type: 'query' },
      routeTag: undefined,
    })
  })

  // ── 失败路径 ──────────────────────────────────────────────────────
  it('refresh 失败：error 为 locale 文案、loading 结束、已有数据不被清空', async () => {
    resolveAdapters(VALID)
    const { adapters, loading, error, refresh } = useQueryAdapters()
    await refresh()
    expect(adapters.value).toEqual(VALID)

    httpMock.get.mockRejectedValueOnce(new Error('network down'))
    await refresh()

    expect(error.value).toBe(LOAD_FAILED_TEXT)
    expect(loading.value).toBe(false)
    expect(adapters.value).toEqual(VALID) // 失败不清空（组件可继续展示旧列表）
  })

  it('失败后再次成功刷新会清除 error', async () => {
    httpMock.get.mockRejectedValueOnce(new Error('boom'))
    const { error, refresh } = useQueryAdapters()
    await refresh()
    expect(error.value).toBe(LOAD_FAILED_TEXT)

    resolveAdapters(VALID)
    await refresh()

    expect(error.value).toBeNull()
  })

  // ── ensure / invalidateCache ─────────────────────────────────────
  it('ensure 首次（无缓存）触发拉取，TTL 内重复调用不再请求', async () => {
    resolveAdapters(VALID)
    const { adapters, ensure } = useQueryAdapters()

    await ensure()
    await ensure()

    expect(httpMock.get).toHaveBeenCalledTimes(1)
    expect(adapters.value).toEqual(VALID)
  })

  it('invalidateCache 后 ensure 会重新拉取', async () => {
    resolveAdapters(VALID)
    const { ensure, invalidateCache } = useQueryAdapters()
    await ensure()
    expect(httpMock.get).toHaveBeenCalledTimes(1)

    invalidateCache()
    await ensure()
    expect(httpMock.get).toHaveBeenCalledTimes(2)
  })

  it('routeTag 透传给 http（PendingView 走 /pending 取消域）', async () => {
    resolveAdapters(VALID)
    const { refresh } = useQueryAdapters('/pending' as RouteTag)

    await refresh()

    expect(httpMock.get).toHaveBeenCalledWith('/adapter/status', {
      params: { type: 'query' },
      routeTag: '/pending',
    })
  })

  // ── 模块级缓存 / 共享状态 ─────────────────────────────────────────
  it('模块级缓存对新实例可见（新实例初始 adapters 即为缓存值）', async () => {
    resolveAdapters(VALID)
    const first = useQueryAdapters()
    await first.refresh()

    const second = useQueryAdapters()

    expect(second.adapters.value).toEqual(VALID)
    // 只是读取缓存，不应产生请求
    expect(httpMock.get).toHaveBeenCalledTimes(1)
  })

  it('loading/error 为模块级共享：一个实例请求中，另一个实例可见 loading=true', async () => {
    let release!: () => void
    httpMock.get.mockReturnValue(
      new Promise((resolve) => {
        release = () => resolve({ data: { adapters: VALID } })
      }),
    )
    const a = useQueryAdapters()
    const b = useQueryAdapters()

    const pending = a.refresh()
    expect(a.loading.value).toBe(true)
    expect(b.loading.value).toBe(true) // 共享同一 ref

    release()
    await pending

    expect(a.loading.value).toBe(false)
    expect(b.loading.value).toBe(false)
    expect(b.error.value).toBeNull()
    expect(a.adapters.value).toEqual(VALID)
  })
})
