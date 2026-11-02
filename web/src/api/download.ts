// web/src/api/download.ts — 标准文件下载
import http from './http'
import type { AxiosResponse } from 'axios'
import type { DownloadResponse } from '../types/api'

export const postDownload = async (numbers: string[], runId?: string): Promise<DownloadResponse> =>
  (await http.post('/download', { numbers, run_id: runId })).data

// 手动导入下载列表：提交标准号文本（FormData，字段名 'text'）
// 纯 click 触发，无需 routeTag（走 globalPool）
export interface DownloadImportResultItem {
  standard_number: string
  standard_name: string
  status: string
  saved_path: string
  error: string
}

export interface DownloadImportResponse {
  valid: string[]
  invalid: string[]
  duplicates: string[]
  total: number
  success: number
  failed: number
  skipped: number
  results: DownloadImportResultItem[]
}

export function postDownloadImport(text: string): Promise<AxiosResponse<DownloadImportResponse>> {
  const formData = new FormData()
  formData.append('text', text)
  return http.post<DownloadImportResponse>('/download/import', formData)
}
