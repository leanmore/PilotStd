// web/src/api/scheduler.ts — 调度器状态
import type { AxiosResponse } from 'axios'
import http from './http'
import type { RouteTag } from '../types/route-tag'

export interface SchedulerJob {
  id: string
  next_run_time: string | null
  trigger: string
  pending: boolean
  last_run_time: string | null
  last_run_status: string | null
  last_error_message: string | null
}

export interface SchedulerStatusResponse {
  running: boolean
  job_count: number
  jobs: SchedulerJob[]
  timestamp: string
}

export function getSchedulerStatus(
  options?: { routeTag?: RouteTag },
): Promise<AxiosResponse<SchedulerStatusResponse>> {
  return http.get<SchedulerStatusResponse>('/scheduler/status', options)
}
