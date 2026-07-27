// web/src/api/validity.ts — 时效性检查 API
import http from './http'

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

export const getValidityConfig = (): Promise<ValidityConfig> =>
  http.get('/validity/config').then(r => r.data)

export const putValidityConfig = (data: Partial<ValidityConfig>): Promise<{ ok: boolean; message: string }> =>
  http.put('/validity/config', data).then(r => r.data)

export const runValidityCheck = (): Promise<ValidityRunResult> =>
  http.post('/validity/run').then(r => r.data)

export const getValidityHistory = (params: {
  page?: number
  page_size?: number
}): Promise<ValidityHistoryResponse> =>
  http.get('/validity/history', { params }).then(r => r.data)

export const enqueueValidityCheck = (filePaths: string[]): Promise<{ ok: boolean; enqueued: number; total: number }> =>
  http.post('/validity/enqueue', { file_paths: filePaths }).then(r => r.data)
