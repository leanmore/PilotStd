// web/src/api/validity.ts — 时效性检查 API
import http from './http'
import type { RouteTag } from '../types/route-tag'

export interface ValidityConfig {
  /** ✅ #43: 首次执行周几（1=周一, 7=周日） */
  first_weekday: number
  /** 执行时间（HH:MM） */
  execute_time: string
  /** 状态更新间隔（周），每条标准检查后的冷却期 */
  total_weeks: number
  /** ✅ #43: 执行频率（周），每隔几周执行一次 */
  frequency_weeks: number
  /** 单批大小（条/批） */
  batch_size: number
  /** 批间隔（秒） */
  batch_interval: number
  /** 检查比例（%） */
  check_ratio: number
}

export interface ValidityRunResult {
  ok: boolean
  message?: string
  checked: number
  changed: number
}

export interface ValidityHistoryItem {
  check_date: string
  checked_count: number
  changed_count: number
  status: string
}

export interface ValidityHistoryResponse {
  total: number
  page: number
  page_size: number
  items: ValidityHistoryItem[]
}

export const getValidityConfig = (routeTag?: RouteTag): Promise<ValidityConfig> =>
  http.get('/validity/config', { routeTag }).then(r => r.data)

export const putValidityConfig = (data: Partial<ValidityConfig>): Promise<{ ok: boolean; message: string }> =>
  http.put('/validity/config', data).then(r => r.data)

export const runValidityCheck = (): Promise<ValidityRunResult> =>
  http.post('/validity/run').then(r => r.data)

export const getValidityHistory = (params: {
  page?: number
  page_size?: number
}, routeTag?: RouteTag): Promise<ValidityHistoryResponse> =>
  http.get('/validity/history', { params, routeTag }).then(r => r.data)

export const enqueueValidityCheck = (filePaths: string[]): Promise<{ ok: boolean; enqueued: number; total: number }> =>
  http.post('/validity/enqueue', { file_paths: filePaths }).then(r => r.data)

/** 解析 "HH:MM" 字符串为 { hour, minute }，空值/非法值容错为 0 */
export function parseExecuteTime(timeStr: string | undefined | null): { hour: number; minute: number } {
  const str = timeStr || '00:00'
  const parts = str.split(':')
  const h = parseInt(parts[0], 10)
  const m = parseInt(parts[1], 10)
  return {
    hour: isNaN(h) ? 0 : Math.min(23, Math.max(0, h)),
    minute: isNaN(m) ? 0 : Math.min(59, Math.max(0, m)),
  }
}

/** 将 { hour, minute } 格式化为 "HH:MM" 字符串（含前导零） */
export function formatExecuteTime(hour: number, minute: number): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(hour)}:${pad(minute)}`
}
