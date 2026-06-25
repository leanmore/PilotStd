// web/src/api/validity.ts — 时效性检查 API
import http from './http'

export interface ValidityConfig {
  frequency: string
  execute_time: string
  batch_size: number
  batch_interval: number
  check_ratio: number
  update_interval: number
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
