// web/src/api/settings.ts — 系统设置与统计 + 静态令牌管理
import http from './http'
import type { Settings, StatusStats } from '../types/api'

export const getSettings = (): Promise<Settings> =>
  http.get('/settings').then(r => r.data)

export const putSettings = (data: Partial<Settings>): Promise<Settings> =>
  http.put('/settings', data).then(r => r.data)

export const getStats = (): Promise<StatusStats> =>
  http.get('/stats').then(r => r.data)

export const getToken = (): Promise<{ token: string }> =>
  http.get('/settings/token').then(r => r.data)

export const refreshToken = (): Promise<{ token: string; refreshed_at: string }> =>
  http.post('/settings/token/refresh').then(r => r.data)
