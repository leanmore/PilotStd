// web/src/api/system.ts — 系统资源监控
import http from './http'
import type { RouteTag } from '../types/route-tag'

export function getSystemResources(options?: { routeTag?: RouteTag }) {
  return http.get('/system/resources', options)
}
