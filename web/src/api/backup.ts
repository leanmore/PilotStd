// web/src/api/backup.ts — 数据库备份管理
import type { AxiosResponse } from 'axios'
import http from './http'
import type { RouteTag } from '../types/route-tag'

export interface BackupItem {
  id: string
  name: string
  size: number
  size_mb: number
  created_at: string
}

export interface BackupListResponse {
  items: BackupItem[]
  count: number
}

export interface BackupCreateResponse {
  ok: boolean
  message: string
}

export function getBackupList(
  options?: { routeTag?: RouteTag },
): Promise<AxiosResponse<BackupListResponse>> {
  return http.get<BackupListResponse>('/backup/list', options)
}

export function createBackup(): Promise<AxiosResponse<BackupCreateResponse>> {
  // click 触发，不加 routeTag（走 globalPool）
  return http.post<BackupCreateResponse>('/backup/create')
}
