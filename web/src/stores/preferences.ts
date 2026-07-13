// web/src/stores/preferences.ts — 统一用户配置管理（JSON 聚合 API）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/http'

export const usePreferencesStore = defineStore('preferences', () => {
  const cache = ref<Record<string, unknown>>({})
  const loading = ref(false)
  const pendingSync = ref<Record<string, boolean>>({})

  async function getAll(): Promise<Record<string, unknown>> {
    loading.value = true
    try {
      const r = await http.get('/api/user-preference')
      const data = r.data?.data || {}
      cache.value = { ...data }
    } catch { /* 后端不可用 */ }
    loading.value = false
    return { ...cache.value }
  }

  function get<T = unknown>(key: string, defaultValue?: T): T | undefined {
    if (key in cache.value && cache.value[key] !== undefined) {
      return cache.value[key] as T
    }
    return defaultValue
  }

  async function set(key: string, value: unknown): Promise<void> {
    cache.value[key] = value
    try {
      await http.patch('/api/user-preference', { updates: cache.value })
      pendingSync.value[key] = false
    } catch {
      pendingSync.value[key] = true
    }
  }

  async function setAll(preferences: Record<string, unknown>): Promise<void> {
    for (const [k, v] of Object.entries(preferences)) {
      cache.value[k] = v
    }
    try {
      await http.patch('/api/user-preference', { updates: cache.value })
    } catch {
      for (const k of Object.keys(preferences)) pendingSync.value[k] = true
    }
  }

  async function remove(key: string): Promise<void> {
    delete cache.value[key]
    try {
      await http.patch('/api/user-preference', { updates: cache.value })
    } catch { /* ignore */ }
  }

  async function resetAll(): Promise<void> {
    try {
      await http.delete('/api/user-preference')
      cache.value = {}
      pendingSync.value = {}
    } catch { /* ignore */ }
  }

  return { cache, loading, get, set, getAll, setAll, remove, resetAll }
})
