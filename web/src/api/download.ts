// web/src/api/download.ts — 标准文件下载
import http from './http'
import type { DownloadResponse } from '../types/api'

export const postDownload = (numbers: string[], runId?: string): Promise<DownloadResponse> =>
  http.post('/download', { numbers, run_id: runId }).then(r => r.data)

// 手动导入下载列表：提交标准号文本（FormData，字段名 'text'）
// 纯 click 触发，无需 routeTag（走 globalPool）
export function postDownloadImport(text: string) {
  const formData = new FormData()
  formData.append('text', text)
  return http.post('/download/import', formData)
}
