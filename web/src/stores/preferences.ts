// web/src/stores/preferences.ts — 统一用户配置管理（RESTful KV API）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/http'
import type { RouteTag } from '@/types/route-tag'

// 系统默认值，对应后端 UserPreferenceManager.DEFAULT_PREFERENCES
// 批量接口返回 {preferences: {key: value}} 扁平结构，此处补全缺失字段的兜底值
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
      // 后端批量接口一次返回全部 KV，替代逐 key 并行 GET
      const { data } = await http.get('/user/preferences', { skipGlobalAuthRedirect: true })
      const assembled: Record<string, unknown> = {}
      _deepMerge(assembled, DEFAULTS)
      if (data?.preferences && typeof data.preferences === 'object') {
        _deepMerge(assembled, data.preferences)
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

  /** 读取仪表盘布局（key 为 layout:dashboard，调用方传入 routeTag 以支持路由级取消） */
  async function getDashboardLayout(routeTag?: RouteTag): Promise<unknown> {
    try {
      const { data } = await http.get('/user/preferences/layout:dashboard', { routeTag })
      return data?.value
    } catch { return null }
  }

  /** 保存仪表盘布局，返回是否成功（供调用方决定降级提示） */
  async function setDashboardLayout(payload: unknown): Promise<boolean> {
    try {
      await http.put('/user/preferences/layout:dashboard', { value: payload })
      return true
    } catch { return false }
  }

  return { cache, loading, get, set, getAll, setAll, getDashboardLayout, setDashboardLayout }
})
