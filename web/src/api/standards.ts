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
  status: string
  last_checked_at: string | null
  next_check_at: string | null
  check_count: number
}

export interface StandardStatusResponse {
  total: number
  page: number
  page_size: number
  items: StandardStatusItem[]
}

export const getStandardsStats = (): Promise<StandardStats> =>
  http.get('/standards/status/stats').then(r => r.data)

export const getStandardsStatus = (params: {
  status?: string
  standard_no?: string
  name?: string
  page?: number
  page_size?: number
}): Promise<StandardStatusResponse> =>
  http.get('/standards/status', { params }).then(r => r.data)
