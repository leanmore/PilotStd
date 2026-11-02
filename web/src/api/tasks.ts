// web/src/api/tasks.ts — 管道运行状态查询 API
import type { AxiosResponse } from 'axios'
import http from './http'
import type { PipelineRun } from '@/types/task'
import type { RouteTag } from '../types/route-tag'

/** 查询管道执行状态（2 秒轮询用） */
export async function getPipelineRun(runId: string): Promise<PipelineRun> {
  return (await http.get(`/tasks/runs/${runId}`)).data
}

export interface TaskItem {
  task_id: string
  task_type: string
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  retry_count: number
  max_retries: number
  queue_name: string
  error_log: string
  result_json: string
  created_at: string
  started_at: string
  finished_at: string
}

export interface TaskListResponse {
  total: number
  page: number
  page_size: number
  items: TaskItem[]
}

export interface TaskCancelResponse {
  ok: boolean
}

export function getTasks(options?: { routeTag?: RouteTag }): Promise<AxiosResponse<TaskListResponse>> {
  return http.get<TaskListResponse>('/tasks', options)
}

export function cancelTask(id: string | number): Promise<AxiosResponse<TaskCancelResponse>> {
  // click 触发，不加 routeTag（走 globalPool）
  return http.post<TaskCancelResponse>(`/tasks/${id}/cancel`)
}


