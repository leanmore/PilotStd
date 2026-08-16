// web/src/utils/taskRestore.ts — 任务进度恢复纯逻辑
// 从后端 step_results（按步骤嵌套）重建前端各步骤结果，供页面重进时恢复详情

import { getItem, removeItem } from '@/lib/storage'
import { getPipelineRun } from '@/api/tasks'
import type { PipelineRun } from '@/types/task'

export interface RestoredResults {
  scan: Record<string, unknown> | null
  query: Record<string, unknown> | null
  download: Record<string, unknown> | null
  normalize: Record<string, unknown> | null
  archive: unknown
}

function step(sr: Record<string, unknown>, name: string): Record<string, unknown> | undefined {
  const v = sr[name]
  return v && typeof v === 'object' ? (v as Record<string, unknown>) : undefined
}

function num(v: unknown, fallback = 0): number {
  return typeof v === 'number' ? v : fallback
}

function list(v: unknown): unknown[] {
  return Array.isArray(v) ? v : []
}

/** 将后端 step_results（可能为 JSON 字符串）映射回各步骤结果，缺失字段回退空值 */
export function restoreResultsFromStepResults(raw: unknown): RestoredResults {
  let sr: Record<string, unknown> = {}
  if (typeof raw === 'string') {
    try { sr = JSON.parse(raw) as Record<string, unknown> } catch { sr = {} }
  } else if (raw && typeof raw === 'object') {
    sr = raw as Record<string, unknown>
  }

  const scan = step(sr, 'scan')
  const query = step(sr, 'query')
  const download = step(sr, 'download')
  const normalize = step(sr, 'normalize')
  const archive = step(sr, 'archive')

  return {
    scan: scan
      ? {
          total: num(scan.total),
          pdf_count: num(scan.pdf_count),
          word_count: num(scan.word_count),
          dup_skipped: num(scan.dup_skipped),
          files: list(scan.files),
        }
      : null,
    query: query
      ? {
          stats: {
            total: num(query.total),
            found: num(query.found),
            downloadable: num(query.downloadable),
            not_found: num(query.not_found),
          },
          results: list(query.results),
        }
      : null,
    download: download
      ? {
          stats: {
            success: num(download.success),
            failed: num(download.failed),
            skipped: num(download.skipped),
          },
          results: list(download.results),
        }
      : null,
    normalize: normalize ? { results: list(normalize.results) } : null,
    archive: archive ? (archive.results ?? null) : null,
  }
}

/** 读取持久化 runId，返回可恢复的运行记录；无记录/终态/失败返回 null 并清理 */
export async function resolveActiveRun(): Promise<{ runId: string; run: PipelineRun } | null> {
  const savedRunId = getItem('task_active_run')
  if (!savedRunId) return null
  try {
    const run = await getPipelineRun(savedRunId)
    if (run.status === 'running' || run.status === 'pending') {
      return { runId: savedRunId, run }
    }
    removeItem('task_active_run')
    return null
  } catch {
    // 后端记录已不存在（如服务重启），清除残留
    removeItem('task_active_run')
    return null
  }
}
