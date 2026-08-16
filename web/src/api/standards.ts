// web/src/api/standards.ts — 标准状态 API
import http from './http'

export interface StandardStats {
  active: number
  inactive: number
  unknown: number
}

export interface StandardStatusItem {
  id: number
  standard_number: string
  standard_name: string
  status: string
  last_checked_at: string | null
  check_count: number
}

export interface StandardStatusResponse {
  total: number
  page: number
  page_size: number
  items: StandardStatusItem[]
}

export const getStandardsStats = (routeTag?: string): Promise<StandardStats> =>
  http.get('/standards/status/stats', { routeTag }).then(r => r.data)

// ── 首屏内存 TTL 缓存（仅 page=1，禁止 localStorage） ──
const CACHE_TTL = 300_000 // 5 分钟
const _cache = new Map<string, { data: StandardStatusResponse; timestamp: number }>()

function _cacheKey(params: { status?: string; name?: string; standard_no?: string }): string {
  return `standards_status:${params.status || ''}:${params.name || ''}:${params.standard_no || ''}`
}

export function clearStandardsStatusCache(): void {
  _cache.clear()
}

export const getStandardsStatus = async (params: {
  status?: string
  standard_no?: string
  name?: string
  page?: number
  page_size?: number
}, routeTag?: string): Promise<StandardStatusResponse> => {
  // page>1 跳过缓存（增量加载页码动态变化）
  if (params.page !== undefined && params.page > 1) {
    return http.get('/standards/status', { params, routeTag }).then(r => r.data)
  }

  const key = _cacheKey(params)
  const cached = _cache.get(key)
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return Promise.resolve(cached.data)
  }

  const r = await http.get('/standards/status', { params, routeTag })
  _cache.set(key, { data: r.data, timestamp: Date.now() })
  return r.data
}
