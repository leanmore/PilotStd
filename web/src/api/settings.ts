// web/src/api/settings.ts — 系统设置与统计 + 静态令牌管理
import http from './http'
import type { Settings, StatusStats } from '../types/api'
import { sessionCache } from '@/utils/cache'

const SETTINGS_CACHE_KEY = 'settings'
let loadingPromise: Promise<Settings> | null = null

export const getSettings = (routeTag?: string): Promise<Settings> =>
  http.get('/settings', { routeTag }).then(r => r.data)

export async function getSettingsCached(routeTag?: string): Promise<Settings> {
  const cached = sessionCache.get<Settings>(SETTINGS_CACHE_KEY)
  if (cached) return cached

  if (loadingPromise) return loadingPromise

  loadingPromise = getSettings(routeTag).then(data => {
    sessionCache.set(SETTINGS_CACHE_KEY, data)
    loadingPromise = null
    return data
  }).catch(err => {
    loadingPromise = null
    throw err
  })

  return loadingPromise
}

export const putSettings = (data: Partial<Settings>): Promise<Settings> =>
  http.put('/settings', data).then(r => r.data)

export const getStats = (routeTag?: string): Promise<StatusStats> =>
  http.get('/stats', { routeTag }).then(r => r.data)

export const getSettingsSchema = (routeTag?: string): Promise<{ tabs: Record<string, any[]> }> =>
  http.get('/settings/schema', { routeTag }).then(r => r.data)

export const getToken = (routeTag?: string): Promise<{ token: string }> =>
  http.get('/settings/token', { routeTag }).then(r => r.data)

export const refreshToken = (): Promise<{ token: string; refreshed_at: string }> =>
  http.post('/settings/token/refresh').then(r => r.data)

export interface TabMeta { key: string; scope: string; order: number; label: string }

export const getSettingsMetadata = (routeTag?: string): Promise<{ tabs: TabMeta[] }> =>
  http.get('/settings/metadata', { routeTag }).then(r => r.data)
