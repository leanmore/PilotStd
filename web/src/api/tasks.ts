// web/src/api/tasks.ts — 管道运行状态查询 API
import http from './http'
import type { PipelineRun } from '@/types/task'
import type { RouteTag } from '../types/route-tag'

/** 查询管道执行状态（2 秒轮询用） */
export function getPipelineRun(runId: string): Promise<PipelineRun> {
  return http.get(`/tasks/runs/${runId}`).then(r => r.data)
}

export function getTasks(options?: { routeTag?: RouteTag }) {
  return http.get('/tasks', options)
}

export function cancelTask(id: string | number) {
  // click 触发，不加 routeTag（走 globalPool）
  return http.post(`/tasks/${id}/cancel`)
}
