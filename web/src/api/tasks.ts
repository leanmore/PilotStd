// web/src/api/tasks.ts — 管道运行状态查询 API
import http from './http'
import type { PipelineRun } from '@/types/task'

/** 查询管道执行状态（2 秒轮询用） */
export function getPipelineRun(runId: string): Promise<PipelineRun> {
  return http.get(`/tasks/runs/${runId}`).then(r => r.data)
}
