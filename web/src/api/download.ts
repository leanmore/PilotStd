// web/src/api/download.ts — 标准文件下载
import http from './http'
import type { DownloadResponse } from '../types/api'

export const postDownload = (numbers: string[]): Promise<DownloadResponse> =>
  http.post('/download', { numbers }).then(r => r.data)
