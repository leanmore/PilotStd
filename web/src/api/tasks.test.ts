// api/tasks.test.ts — 管道运行状态 / 任务列表（NEW-44）
//
// 契约：getPipelineRun 取 .data（轮询直接消费）；stop/final 放 query、body 为 undefined；
// getTasks 返回**完整 AxiosResponse**；cancelTask 路径插值且不附 options（click 触发走
// globalPool）。失败一律原样透传。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import {
  cancelTask,
  getPipelineRun,
  getTasks,
  resumePipelineRun,
  stopPipelineRun,
} from './tasks'

describe('tasks API：管道运行控制', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPipelineRun 走 GET /tasks/runs/:id，返回 .data', async () => {
    const run = { run_id: 'run-1', status: 'running', stage: 'scan' }
    h.get.mockResolvedValueOnce({ data: run })

    await expect(getPipelineRun('run-1')).resolves.toEqual(run)
    expect(h.get).toHaveBeenCalledWith('/tasks/runs/run-1')
  })

  it('stopPipelineRun 默认 final=false 放 query，body 为 undefined', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true } })

    await stopPipelineRun('run-1')

    expect(h.post).toHaveBeenCalledWith('/tasks/runs/run-1/stop', undefined, {
      params: { final: false },
    })
  })

  it('stopPipelineRun final=true 时确认进入 stopped（query 显式 true）', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true } })

    await expect(stopPipelineRun('run-1', true)).resolves.toEqual({ ok: true })
    expect(h.post).toHaveBeenCalledWith('/tasks/runs/run-1/stop', undefined, {
      params: { final: true },
    })
  })

  it('resumePipelineRun 走 POST /tasks/runs/:id/resume（恢复被重启中断的管道）', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true } })

    await resumePipelineRun('run-9')

    expect(h.post).toHaveBeenCalledWith('/tasks/runs/run-9/resume')
    expect(h.post.mock.calls[0][2]).toBeUndefined()
  })
})

describe('tasks API：任务列表 / 取消', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getTasks 透传 options 并返回完整 AxiosResponse', async () => {
    const response = { status: 200, data: { total: 0, page: 1, page_size: 20, items: [] } }
    h.get.mockResolvedValueOnce(response)

    const result = await getTasks({ routeTag: '/task' })

    expect(h.get).toHaveBeenCalledWith('/tasks', { routeTag: '/task' })
    expect(result).toBe(response)

    await getTasks()
    expect(h.get).toHaveBeenLastCalledWith('/tasks', undefined)
  })

  it('cancelTask 路径插值，数字/字符串 id 均可，且不附加 options', async () => {
    h.post.mockResolvedValue({ data: { ok: true } })

    await cancelTask(42)
    await cancelTask('task-7')

    expect(h.post).toHaveBeenNthCalledWith(1, '/tasks/42/cancel')
    expect(h.post).toHaveBeenNthCalledWith(2, '/tasks/task-7/cancel')
  })

  it('失败原样透传（轮询/停止失败由调用方处理）', async () => {
    const err = new Error('run not found')
    h.get.mockRejectedValueOnce(err)

    await expect(getPipelineRun('missing')).rejects.toBe(err)
  })
})
