// web/src/api/settings.ts — 系统设置与统计 + 静态令牌管理
import http from './http'
import type { RouteTag } from '../types/route-tag'
import type { Settings, StatusStats, LoginBackgroundResponse } from '../types/api'
import { sessionCache } from '@/utils/cache'

const SETTINGS_CACHE_KEY = 'settings'
let loadingPromise: Promise<Settings> | null = null

export const getSettings = async (routeTag?: RouteTag): Promise<Settings> =>
  (await http.get('/settings', { routeTag })).data

/** 登录页背景图 URL（公开接口，无需登录态）。
 *
 * 解耦 admin-only 的 GET /api/settings：未登录访问 settings 会 401，
 * 导致登录页背景图延迟/缺失；此接口仅返回 appearance.login_bg 单字段。 */
export const getLoginBackground = async (): Promise<LoginBackgroundResponse> =>
  (await http.get('/login-background')).data

export async function getSettingsCached(routeTag?: RouteTag): Promise<Settings> {
  const cached = sessionCache.get<Settings>(SETTINGS_CACHE_KEY)
  if (cached) return cached

  if (loadingPromise) return loadingPromise

  loadingPromise = (async () => {
    try {
      const data = await getSettings(routeTag)
      sessionCache.set(SETTINGS_CACHE_KEY, data)
      return data
    } finally {
      // 成功/失败都清空共享 promise，避免下次调用复用已结算的结果；
      // 失败时异常由 finally 原样透出（原 .catch 是 `throw err`，非吞掉）
      loadingPromise = null
    }
  })()

  return loadingPromise
}

export const putSettings = async (data: Partial<Settings>): Promise<Settings> =>
  (await http.put('/settings', data)).data

export const getStats = async (routeTag?: RouteTag): Promise<StatusStats> =>
  (await http.get('/stats', { routeTag })).data

export const getSettingsSchema = async (routeTag?: RouteTag): Promise<{ tabs: Record<string, any[]> }> =>
  (await http.get('/settings/schema', { routeTag })).data

export const getToken = async (routeTag?: RouteTag): Promise<{ token: string }> =>
  (await http.get('/settings/token', { routeTag })).data

export const refreshToken = async (): Promise<{ token: string; refreshed_at: string }> =>
  (await http.post('/settings/token/refresh')).data

export interface TabMeta { key: string; scope: string; order: number; label: string }

export const getSettingsMetadata = async (routeTag?: RouteTag): Promise<{ tabs: TabMeta[] }> =>
  (await http.get('/settings/metadata', { routeTag })).data
