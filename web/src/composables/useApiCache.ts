// web/src/composables/useApiCache.ts
// 简单 TTL 内存缓存 — 避免短时间内重复请求慢变化 API（settings/adapter status 等）

const cache = new Map<string, { data: unknown; ts: number }>()

export function useApiCache() {
  /**
   * 带 TTL 的缓存获取。缓存命中且未过期则直接返回，否则执行 fetcher 并缓存。
   * @param key 缓存键
   * @param fetcher 数据获取函数
   * @param ttlMs 缓存有效期（毫秒），默认 30s
   */
  async function getCached<T>(key: string, fetcher: () => Promise<T>, ttlMs = 30000): Promise<T> {
    const entry = cache.get(key)
    if (entry && Date.now() - entry.ts < ttlMs) {
      return entry.data as T
    }
    const data = await fetcher()
    cache.set(key, { data, ts: Date.now() })
    return data as T
  }

  /** 使指定的缓存 key 失效 */
  function invalidate(key?: string) {
    if (key) cache.delete(key)
    else cache.clear()
  }

  return { getCached, invalidate }
}
