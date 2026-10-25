// web/src/api/files.ts — 文件浏览、扫描、整理、上传
import http from './http'
import type { RouteTag } from '../types/route-tag'
import type { ListFilesResponse, ScanResponse, NormalizeResult, SuccessResponse, CleanResponse, UploadResponse } from '../types/api'

export const getFiles = async (path: string, routeTag?: RouteTag): Promise<ListFilesResponse> =>
  (await http.get('/files', { params: { path }, routeTag })).data

export const postScan = async (path: string, recursive: boolean = true, runId?: string): Promise<ScanResponse> =>
  (await http.post('/scan', { run_id: runId || null }, { params: { path, recursive: String(recursive) } })).data

export const postNormalize = async (items: NormalizeResult[], runId: string): Promise<{ results: NormalizeResult[] }> =>
  (await http.post('/normalize', { items, run_id: runId })).data

export const postArchive = async (items: NormalizeResult[], word_source_root?: string, runId?: string): Promise<SuccessResponse> =>
  (await http.post('/archive', { items, word_source_root, run_id: runId })).data

export const postCleanEmpty = async (path: string): Promise<CleanResponse> =>
  (await http.post('/clean-empty', null, { params: { path } })).data

export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const fd = new FormData()
  fd.append('file', file)
  return (await http.post('/upload', fd)).data
}
