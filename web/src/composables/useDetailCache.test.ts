// web/src/composables/useDetailCache.test.ts — 公告详情 sessionStorage 缓存单元测试
//
// NEW-44 补齐：此前 `useDetailCache.ts` 无任何测试。本文件锁定**对外契约**：
//   · 键名格式 `detail_<source>_<announceNo>`（列表→详情复用同一 key，跨来源隔离）
//   · set 写入数据并附加 `_ts`；get 命中返回完整对象
//   · TTL 30 分钟兜底过期：恰好到期即失效并主动删除（边界 `>=`）
//   · 脏数据（非法 JSON / 缺 `_ts` / null）安全回落 null，不抛异常
//   · clear 只清自己的键；sessionStorage 写入异常时 set 静默降级（不阻断页面）
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useDetailCache } from './useDetailCache'

const TTL_MS = 30 * 60 * 1000
const keyOf = (source: string, no: string) => `detail_${source}_${no}`

/** 预置缓存（方便直接构造 `_ts`，绕开 set 的 Date.now()） */
function seed(source: string, no: string, payload: unknown): void {
  sessionStorage.setItem(keyOf(source, no), JSON.stringify(payload))
}

describe('useDetailCache', () => {
  afterEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('无缓存时 get 返回 null，且不写任何键', () => {
    expect(useDetailCache('gb', '2026-1').get()).toBeNull()
    expect(sessionStorage.getItem(keyOf('gb', '2026-1'))).toBeNull()
  })

  it('set 写入数据并附加 _ts；get 命中返回完整对象（键名契约）', () => {
    const cache = useDetailCache('gb', '2026-1')
    const before = Date.now()
    cache.set({ announce_no: '2026-1', title: '标题' })

    const hit = cache.get()
    expect(hit).toMatchObject({ announce_no: '2026-1', title: '标题' })
    expect(typeof hit!._ts).toBe('number')
    expect(hit!._ts).toBeGreaterThanOrEqual(before)
    // 其他消费方（列表返回再进详情）依赖同一 key 命中
    expect(sessionStorage.getItem(keyOf('gb', '2026-1'))).not.toBeNull()
  })

  it('不同 source / announceNo 的缓存互相隔离', () => {
    useDetailCache('gb', '2026-1').set({ title: '国标 1' })
    useDetailCache('hb', '2026-1').set({ title: '行标 1' })
    useDetailCache('gb', '2026-2').set({ title: '国标 2' })

    expect(useDetailCache('gb', '2026-1').get()).toMatchObject({ title: '国标 1' })
    expect(useDetailCache('hb', '2026-1').get()).toMatchObject({ title: '行标 1' })
    expect(useDetailCache('gb', '2026-2').get()).toMatchObject({ title: '国标 2' })
    expect(useDetailCache('hb', '2026-2').get()).toBeNull()
  })

  it('TTL 内（剩 1 分钟）命中，返回对象保留原字段', () => {
    seed('gb', '2026-1', { title: '标题', _ts: Date.now() - TTL_MS + 60_000 })

    expect(useDetailCache('gb', '2026-1').get()).toMatchObject({ title: '标题' })
    expect(sessionStorage.getItem(keyOf('gb', '2026-1'))).not.toBeNull()
  })

  it('恰好到期（_ts = now - 30min）即失效，并主动删除缓存条目', () => {
    seed('gb', '2026-1', { title: '标题', _ts: Date.now() - TTL_MS })

    expect(useDetailCache('gb', '2026-1').get()).toBeNull()
    expect(sessionStorage.getItem(keyOf('gb', '2026-1'))).toBeNull()
  })

  it('非法 JSON：get 回落 null 并删除脏条目，不抛异常', () => {
    sessionStorage.setItem(keyOf('gb', '2026-1'), '{not-json')

    expect(() => useDetailCache('gb', '2026-1').get()).not.toThrow()
    expect(useDetailCache('gb', '2026-1').get()).toBeNull()
    expect(sessionStorage.getItem(keyOf('gb', '2026-1'))).toBeNull()
  })

  it('缺 _ts / JSON null：get 回落 null（不误当作有效缓存）', () => {
    seed('gb', '2026-1', { title: '旧格式' })
    seed('gb', '2026-2', null)

    expect(useDetailCache('gb', '2026-1').get()).toBeNull()
    expect(useDetailCache('gb', '2026-2').get()).toBeNull()
  })

  it('set 覆盖旧值：get 返回最近一次写入', () => {
    const cache = useDetailCache('gb', '2026-1')
    cache.set({ title: '旧' })
    cache.set({ title: '新' })

    expect(cache.get()).toMatchObject({ title: '新' })
  })

  it('clear 只删除自己的键，不影响其他缓存', () => {
    useDetailCache('gb', '2026-1').set({ title: '待清' })
    useDetailCache('gb', '2026-2').set({ title: '保留' })

    useDetailCache('gb', '2026-1').clear()

    expect(useDetailCache('gb', '2026-1').get()).toBeNull()
    expect(useDetailCache('gb', '2026-2').get()).toMatchObject({ title: '保留' })
  })

  it('sessionStorage 写入异常（配额满）时 set 静默降级、不抛异常', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })

    expect(() => useDetailCache('gb', '2026-1').set({ title: '写不进' })).not.toThrow()
  })
})
