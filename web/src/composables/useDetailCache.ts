// web/src/composables/useDetailCache.ts
// 公告详情 sessionStorage 缓存 — 解决返回列表再进入重复加载的问题

const CACHE_TTL = 30 * 60 * 1000 // 30 分钟兜底过期；数据变更时主动清除

export function useDetailCache(source: string, announceNo: string) {
  const cacheKey = `detail_${source}_${announceNo}`

  function clear(): void {
    sessionStorage.removeItem(cacheKey)
  }

  function get(): Record<string, any> | null {
    const raw = sessionStorage.getItem(cacheKey)
    if (!raw) return null
    try {
      const cached = JSON.parse(raw)
      if (!cached || typeof cached._ts !== 'number') return null
      if (Date.now() - cached._ts >= CACHE_TTL) {
        sessionStorage.removeItem(cacheKey)
        return null
      }
      return cached
    } catch {
      sessionStorage.removeItem(cacheKey)
      return null
    }
  }

  function set(data: Record<string, any>): void {
    try {
      sessionStorage.setItem(cacheKey, JSON.stringify({ ...data, _ts: Date.now() }))
    } catch {
      // sessionStorage 满了，忽略（不影响功能）
    }
  }

  return { get, set, clear }
}
