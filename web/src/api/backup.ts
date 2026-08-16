// web/src/api/backup.ts — 数据库备份管理
import http from './http'
import type { RouteTag } from '../types/route-tag'

export function getBackupList(options?: { routeTag?: RouteTag }) {
  return http.get('/backup/list', options)
}

export function createBackup() {
  // click 触发，不加 routeTag（走 globalPool）
  return http.post('/backup/create')
}
