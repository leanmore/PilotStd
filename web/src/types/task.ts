// web/src/types/task.ts — 任务管道运行追踪类型定义

/** 管道五步阶段 */
export type PipelineStep = 'scan' | 'query' | 'download' | 'normalize' | 'archive'

/** 管道运行状态 */
export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed'

/** 管道运行记录（对应 GET /api/tasks/runs/{run_id} 响应） */
export interface PipelineRun {
  run_id: string
  current_step: PipelineStep
  status: PipelineStatus
  progress: number // 0–100
  step_results: Record<string, unknown>
  error_message: string
  created_at: string
  updated_at: string
}
