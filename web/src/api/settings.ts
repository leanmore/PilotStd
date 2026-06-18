// web/src/api/settings.ts — 系统设置与统计
import http from './http'
import type { Settings, StatusStats } from '../types/api'

export const getSettings = (): Promise<Settings> =>
  http.get('/settings').then(r => r.data)

export const putSettings = (data: Partial<Settings>): Promise<Settings> =>
  http.put('/settings', data).then(r => r.data)

export const getStats = (): Promise<StatusStats> =>
  http.get('/stats').then(r => r.data)
