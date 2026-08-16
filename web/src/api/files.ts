// web/src/api/files.ts — 文件浏览、扫描、整理、上传
import http from './http'
import type { RouteTag } from '../types/route-tag'
import type { ListFilesResponse, ScanResponse, NormalizeResult, SuccessResponse, CleanResponse, UploadResponse } from '../types/api'

export const getFiles = (path: string, routeTag?: RouteTag): Promise<ListFilesResponse> =>
  http.get('/files', { params: { path }, routeTag }).then(r => r.data)

export const postScan = (path: string, recursive: boolean = true, runId?: string): Promise<ScanResponse> =>
  http.post('/scan', { run_id: runId || null }, { params: { path, recursive: String(recursive) } }).then(r => r.data)

export const postNormalize = (items: NormalizeResult[], runId: string): Promise<{ results: NormalizeResult[] }> =>
  http.post('/normalize', { items, run_id: runId }).then(r => r.data)

export const postArchive = (items: NormalizeResult[], word_source_root?: string, runId?: string): Promise<SuccessResponse> =>
  http.post('/archive', { items, word_source_root, run_id: runId }).then(r => r.data)

export const postCleanEmpty = (path: string): Promise<CleanResponse> =>
  http.post('/clean-empty', null, { params: { path } }).then(r => r.data)

export const uploadFile = (file: File): Promise<UploadResponse> => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/upload', fd).then(r => r.data)
}
