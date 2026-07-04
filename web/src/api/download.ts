// web/src/api/download.ts — 标准文件下载
import http from './http'
import type { DownloadResponse } from '../types/api'

export const postDownload = (numbers: string[], runId?: string): Promise<DownloadResponse> =>
  http.post('/download', { numbers, run_id: runId }).then(r => r.data)
