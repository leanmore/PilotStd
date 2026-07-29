// web/src/composables/useApiCache.ts
// TTL 内存缓存 + LRU 淘汰 — 避免短时间内重复请求，防止无限增长

interface CacheEntry<T = unknown> {
  data: T
  ts: number
  lastAccess: number
}

/** 缓存默认 TTL（毫秒） */
const DEFAULT_TTL_MS = 5 * 60 * 1000
/** 最大条目数，超限时淘汰最久未访问条目 */
const MAX_ENTRIES = 200

const cache = new Map<string, CacheEntry>()

/** 清理所有过期条目。 */
function _cleanup() {
  const now = Date.now()
  for (const [key, entry] of cache) {
    if (now - entry.ts > DEFAULT_TTL_MS) {
      cache.delete(key)
    }
  }
}

/** LRU 淘汰：删除 lastAccess 最旧的条目直到低于上限。 */
function _evict() {
  if (cache.size <= MAX_ENTRIES) return
  const sorted = [...cache.entries()].sort((a, b) => a[1].lastAccess - b[1].lastAccess)
  const toRemove = sorted.slice(0, cache.size - MAX_ENTRIES)
  for (const [key] of toRemove) {
    cache.delete(key)
  }
}

export function useApiCache() {
  /**
   * 带 TTL 的缓存获取。命中则返回缓存；过期或未命中则执行 fetcher 并缓存。
   * @param key    缓存键
   * @param fetcher 数据获取函数
   * @param ttlMs  缓存有效期（毫秒），默认 5 分钟
   */
  async function getCached<T>(key: string, fetcher: () => Promise<T>, ttlMs = DEFAULT_TTL_MS): Promise<T> {
    const entry = cache.get(key)
    if (entry) {
      if (Date.now() - entry.ts < ttlMs) {
        entry.lastAccess = Date.now()
        return entry.data as T
      }
      cache.delete(key)
    }
    const data = await fetcher()
    cache.set(key, { data, ts: Date.now(), lastAccess: Date.now() })
    // 每次写入后触发清理 + LRU 淘汰
    _cleanup()
    _evict()
    return data as T
  }

  /** 使指定 key 失效（不传 key 则清空全部）。 */
  function invalidate(key?: string) {
    if (key) cache.delete(key)
    else cache.clear()
  }

  /** 手动清理所有过期条目（外部可调用）。 */
  function cleanup() {
    _cleanup()
  }

  return { getCached, invalidate, cleanup }
}
