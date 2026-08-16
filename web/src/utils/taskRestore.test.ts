// web/src/utils/taskRestore.test.ts
// 覆盖 step_results 映射、缺失字段回退、runId 恢复/终态清理逻辑

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { restoreResultsFromStepResults, resolveActiveRun } from './taskRestore'
import { setItem } from '@/lib/storage'
import { getPipelineRun } from '@/api/tasks'
import type { PipelineRun } from '@/types/task'

vi.mock('@/api/tasks', () => ({
  getPipelineRun: vi.fn(),
}))

const mockGet = vi.mocked(getPipelineRun)

function makeRun(overrides: Partial<PipelineRun> = {}): PipelineRun {
  return {
    run_id: 'run-1',
    current_step: 'query',
    status: 'running',
    progress: 40,
    step_results: {},
    error_message: '',
    created_at: '2026-08-16 00:00:00',
    updated_at: '2026-08-16 00:00:00',
    ...overrides,
  }
}

describe('restoreResultsFromStepResults', () => {
  it('完整 step_results 正确映射各步骤', () => {
    const result = restoreResultsFromStepResults({
      scan: { total: 10, pdf_count: 8, word_count: 2, dup_skipped: 0, files: [{ name: 'a.pdf' }] },
      query: { total: 10, found: 5, downloadable: 3, not_found: 5, results: [{ standard_number: 'GB/T 1' }] },
      download: { success: 3, failed: 1, skipped: 0, results: [{ status: 'success' }] },
      normalize: { count: 5, results: [{ source_path: '/a', new_filename: 'b' }] },
      archive: { count: 5, results: { moved: 5 } },
    })
    expect(result.scan).toEqual({ total: 10, pdf_count: 8, word_count: 2, dup_skipped: 0, files: [{ name: 'a.pdf' }] })
    expect(result.query).toEqual({ stats: { total: 10, found: 5, downloadable: 3, not_found: 5 }, results: [{ standard_number: 'GB/T 1' }] })
    expect(result.download).toEqual({ stats: { success: 3, failed: 1, skipped: 0 }, results: [{ status: 'success' }] })
    expect(result.normalize).toEqual({ results: [{ source_path: '/a', new_filename: 'b' }] })
    expect(result.archive).toEqual({ moved: 5 })
  })

  it('空对象返回全 null', () => {
    const result = restoreResultsFromStepResults({})
    expect(result.scan).toBeNull()
    expect(result.query).toBeNull()
    expect(result.download).toBeNull()
    expect(result.normalize).toBeNull()
    expect(result.archive).toBeNull()
  })

  it('字符串 JSON 正确解析', () => {
    const result = restoreResultsFromStepResults(JSON.stringify({ scan: { total: 3 } }))
    expect(result.scan).toEqual({ total: 3, pdf_count: 0, word_count: 0, dup_skipped: 0, files: [] })
  })

  it('缺失字段回退空值不报错', () => {
    const result = restoreResultsFromStepResults({
      scan: { total: 5 },
      query: { found: 2 },
    })
    expect(result.scan).toEqual({ total: 5, pdf_count: 0, word_count: 0, dup_skipped: 0, files: [] })
    expect(result.query).toEqual({ stats: { total: 0, found: 2, downloadable: 0, not_found: 0 }, results: [] })
  })

  it('非法字符串解析失败回退全 null', () => {
    const result = restoreResultsFromStepResults('not-json')
    expect(result.scan).toBeNull()
  })
})

describe('resolveActiveRun', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('无持久化 runId 返回 null 且不请求', async () => {
    const result = await resolveActiveRun()
    expect(result).toBeNull()
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('running 任务返回 runId 和 run', async () => {
    setItem('task_active_run', 'run-1')
    mockGet.mockResolvedValueOnce(makeRun({ status: 'running' }))
    const result = await resolveActiveRun()
    expect(result).toEqual({ runId: 'run-1', run: expect.objectContaining({ status: 'running' }) })
  })

  it('completed 任务返回 null 并清除记录', async () => {
    setItem('task_active_run', 'run-1')
    mockGet.mockResolvedValueOnce(makeRun({ status: 'completed' }))
    const result = await resolveActiveRun()
    expect(result).toBeNull()
    expect(localStorage.getItem('pilotstd_task_active_run')).toBeNull()
  })

  it('查询失败返回 null 并清除记录', async () => {
    setItem('task_active_run', 'run-1')
    mockGet.mockRejectedValueOnce(new Error('not found'))
    const result = await resolveActiveRun()
    expect(result).toBeNull()
    expect(localStorage.getItem('pilotstd_task_active_run')).toBeNull()
  })
})
