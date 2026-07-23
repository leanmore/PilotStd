// web/src/utils/cache.ts — 会话级内存缓存
// Q33: 避免同会话内重复请求 /api/settings

export const sessionCache = {
  _cache: new Map<string, unknown>(),

  get<T>(key: string): T | null {
    const val = this._cache.get(key)
    return (val as T) ?? null
  },

  set<T>(key: string, value: T): void {
    this._cache.set(key, value)
  },

  clear(): void {
    this._cache.clear()
  },
}
