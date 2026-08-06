// web/src/stores/preferences.ts — 统一用户配置管理（RESTful KV API）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/http'

// 系统默认值，对应后端 UserPreferenceManager.DEFAULT_PREFERENCES
// 新 API 返回 {key, value} 扁平结构，此处补全缺失字段的兜底值
const DEFAULTS: Record<string, unknown> = {
  ui: {
    theme: 'light',
    language: 'zh-CN',
    compact_mode: false,
    items_per_page: 20,
  },
  search: {
    default_standard_type: 'GB/T',
    auto_open_details: true,
    recent_limit: 10,
  },
  notifications: {
    email_enabled: true,
    desktop_popup: true,
    sound_enabled: false,
  },
  download: {
    auto_organize: true,
    overwrite: false,
  },
  layouts: {
    home: {},
    search: {},
    detail: {},
  },
}

// 需要从后端拉取的全部顶层 key（与 DEFAULTS + 组件动态写入的 key 并集）
const TOP_KEYS = [
  'ui', 'search', 'notifications', 'download', 'layouts',
  'sidebar_collapsed', 'announce_since_date', 'system_sections',
  'task_path', 'notification_quiet_hours',
]

function _deepMerge(target: Record<string, unknown>, source: Record<string, unknown>) {
  for (const key of Object.keys(source)) {
    const sv = source[key]
    if (sv && typeof sv === 'object' && !Array.isArray(sv)) {
      const tv = target[key]
      if (!tv || typeof tv !== 'object' || Array.isArray(tv)) {
        target[key] = {}
      }
      _deepMerge(target[key] as Record<string, unknown>, sv as Record<string, unknown>)
    } else {
      target[key] = sv
    }
  }
}

export const usePreferencesStore = defineStore('preferences', () => {
  const cache = ref<Record<string, unknown>>({})
  const loading = ref(false)
  const pendingSync = ref<Record<string, boolean>>({})

  async function getAll(): Promise<Record<string, unknown>> {
    loading.value = true
    try {
      const results = await Promise.allSettled(
        TOP_KEYS.map(k =>
          http.get(`/user/preferences/${encodeURIComponent(k)}`, { skipGlobalAuthRedirect: true }),
        ),
      )
      const assembled: Record<string, unknown> = {}
      _deepMerge(assembled, DEFAULTS)
      for (let i = 0; i < TOP_KEYS.length; i++) {
        const r = results[i]
        if (r.status === 'fulfilled' && r.value?.data?.value != null) {
          assembled[TOP_KEYS[i]] = r.value.data.value
        }
      }
      cache.value = assembled
    } catch { /* 后端不可用，保持现有缓存 */ }
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
      await http.put(`/user/preferences/${encodeURIComponent(key)}`, { value })
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
      await http.put('/user/preferences', { preferences })
    } catch {
      for (const k of Object.keys(preferences)) pendingSync.value[k] = true
    }
  }

  async function remove(key: string): Promise<void> {
    delete cache.value[key]
    try {
      await http.delete(`/user/preferences/${encodeURIComponent(key)}`)
    } catch { /* ignore */ }
  }

  async function resetAll(): Promise<void> {
    try {
      await Promise.allSettled(
        TOP_KEYS.map(k => http.delete(`/user/preferences/${encodeURIComponent(k)}`)),
      )
    } catch { /* ignore */ }
    cache.value = {}
    _deepMerge(cache.value, DEFAULTS)
    pendingSync.value = {}
  }

  return { cache, loading, get, set, getAll, setAll, remove, resetAll }
})
