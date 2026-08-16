// web/src/api/scheduler.ts — 调度器状态
import http from './http'
import type { RouteTag } from '../types/route-tag'

export function getSchedulerStatus(options?: { routeTag?: RouteTag }) {
  return http.get('/scheduler/status', options)
}
