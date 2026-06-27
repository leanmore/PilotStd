// web/src/stores/preferences.ts — 统一用户配置管理
import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/http'

const PREF_PREFIX = 'pref_'

export const usePreferencesStore = defineStore('preferences', () => {
  const cache = ref<Record<string, unknown>>({})
  const pendingSync = ref<Record<string, boolean>>({})
  const loading = ref(false)

  /** 获取单个配置项（后端 → localStorage → 默认值） */
  async function get<T = unknown>(key: string, defaultValue?: T): Promise<T | undefined> {
    if (cache.value[key] !== undefined) return cache.value[key] as T

    try {
      const r = await http.get(`/user/preferences/${encodeURIComponent(key)}`)
      const val = r.data?.value
      if (val !== null && val !== undefined) {
        cache.value[key] = val
        syncLocal(key, val)
        return val as T
      }
    } catch { /* 降级 */ }

    return getLocal(key, defaultValue)
  }

  /** 设置单个配置项（后端优先 + localStorage 备份） */
  async function set(key: string, value: unknown): Promise<void> {
    cache.value[key] = value
    syncLocal(key, value)

    try {
      await http.put(`/user/preferences/${encodeURIComponent(key)}`, { value })
      pendingSync.value[key] = false
    } catch {
      pendingSync.value[key] = true
    }
  }

  /** 批量获取 */
  async function getAll(): Promise<Record<string, unknown>> {
    try {
      const r = await http.get('/user/preferences')
      const prefs = r.data?.preferences || {}
      for (const [k, v] of Object.entries(prefs)) {
        cache.value[k] = v
        syncLocal(k, v)
      }
      return prefs as Record<string, unknown>
    } catch {
      return cache.value
    }
  }

  /** 批量保存 */
  async function setAll(preferences: Record<string, unknown>): Promise<void> {
    for (const [k, v] of Object.entries(preferences)) {
      cache.value[k] = v
      syncLocal(k, v)
    }
    try {
      await http.put('/user/preferences', { preferences })
    } catch {
      for (const k of Object.keys(preferences)) pendingSync.value[k] = true
    }
  }

  /** 删除配置项（恢复默认） */
  async function remove(key: string): Promise<void> {
    delete cache.value[key]
    localStorage.removeItem(PREF_PREFIX + key)
    try {
      await http.delete(`/user/preferences/${encodeURIComponent(key)}`)
    } catch { /* ignore */ }
  }

  /** 重试同步待同步项 */
  async function retryPending(): Promise<void> {
    const pending = Object.entries(pendingSync.value).filter(([, v]) => v)
    if (pending.length === 0) return
    const prefs: Record<string, unknown> = {}
    for (const [key] of pending) {
      const local = getLocalRaw(key)
      if (local) prefs[key] = local
    }
    if (Object.keys(prefs).length === 0) return
    try {
      await http.put('/user/preferences', { preferences: prefs })
      for (const k of Object.keys(prefs)) pendingSync.value[k] = false
    } catch { /* 下次重试 */ }
  }

  function syncLocal(key: string, value: unknown) {
    try {
      localStorage.setItem(PREF_PREFIX + key, JSON.stringify(value))
    } catch { /* ignore quota */ }
  }

  function getLocal<T>(key: string, defaultValue?: T): T | undefined {
    const raw = getLocalRaw(key)
    if (raw !== null) return raw as T
    return defaultValue
  }

  function getLocalRaw(key: string): unknown | null {
    try {
      const raw = localStorage.getItem(PREF_PREFIX + key)
      if (raw) return JSON.parse(raw)
    } catch { /* ignore */ }
    return null
  }

  return { cache, loading, get, set, getAll, setAll, remove, retryPending }
})
