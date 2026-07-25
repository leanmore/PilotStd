// web/src/api/validity.ts — 时效性检查 API
import http from './http'

export interface ValidityConfig {
  execute_time: string
  batch_size: number
  batch_interval: number
  check_ratio: number
  /** 状态更新间隔（周），每条标准检查后的冷却期 */
  total_weeks: number
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

export const putValidityConfig = (data: ValidityConfig): Promise<{ ok: boolean; message: string }> =>
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
