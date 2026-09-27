// web/src/composables/useQueryAdapters.ts
// 查询适配器列表 — 模块级缓存 + TTL，供 PendingView 等组件使用

import { ref, type Ref } from 'vue'
import http from '@/api/http'
import type { RouteTag } from '@/types/route-tag'
import type { QueryAdapterItem } from '@/types/adapter'
import { i18n } from '@/i18n'

/** 非组件模块：用全局实例翻译（错误文案在赋值瞬间解析） */
const t = (key: string) => i18n.global.t(key) as string

// 模块级缓存（全局单例）
let cached: QueryAdapterItem[] | null = null
let lastFetch = 0
const DEFAULT_TTL = 300_000  // 5 分钟

// 共享状态（所有调用者看到同一份 loading/error）
const loading = ref(false)
const error = ref<string | null>(null)

function isExpired(): boolean {
  return !cached || Date.now() - lastFetch > DEFAULT_TTL
}

async function _fetch(routeTag?: RouteTag): Promise<QueryAdapterItem[]> {
  const r = await http.get('/adapter/status', { params: { type: 'query' }, routeTag })
  const raw = r.data?.adapters || []
  const items: QueryAdapterItem[] = []
  for (const item of raw) {
    if (item.name && item.display_name) {
      items.push({ name: item.name, display_name: item.display_name })
    } else {
      console.warn('[useQueryAdapters] 过滤脏数据:', item) // i18n-allow: 开发者日志：过滤脏数据
    }
  }
  return items
}

export function useQueryAdapters(routeTag?: RouteTag) {
  const adapters = ref<QueryAdapterItem[]>(cached || []) as Ref<QueryAdapterItem[]>

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      cached = await _fetch(routeTag)
      lastFetch = Date.now()
      adapters.value = cached
    } catch {
      error.value = t('query_adapters.load_failed')
    } finally {
      loading.value = false
    }
  }

  async function ensure(): Promise<void> {
    if (isExpired()) {
      await refresh()
    }
  }

  function invalidateCache(): void {
    cached = null
    lastFetch = 0
  }

  return { adapters, loading, error, ensure, refresh, invalidateCache }
}
