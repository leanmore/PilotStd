// api/scheduler.test.ts — 调度器状态（NEW-44）
//
// 契约：GET /scheduler/status，透传 options（routeTag 供路由切换时精确取消）；
// **返回完整 AxiosResponse**（SchedulerStatus 视图要读 status 判断后端是否可用）。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import { getSchedulerStatus } from './scheduler'

describe('scheduler API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getSchedulerStatus 走 GET /scheduler/status 并透传 routeTag', async () => {
    const response = {
      status: 200,
      data: { running: true, job_count: 1, jobs: [], timestamp: '2026-11-25T00:00:00Z' },
    }
    h.get.mockResolvedValueOnce(response)

    const result = await getSchedulerStatus({ routeTag: '/scheduler' })

    expect(h.get).toHaveBeenCalledWith('/scheduler/status', { routeTag: '/scheduler' })
    // 返回引用必须就是 AxiosResponse 本身：调用方会读 status
    expect(result).toBe(response)
  })

  it('无参数时 options 为 undefined（走全局降级池，登出时可被 cancelAllRequests 取消）', async () => {
    h.get.mockResolvedValueOnce({ status: 200, data: { running: false } })

    await getSchedulerStatus()

    expect(h.get).toHaveBeenCalledWith('/scheduler/status', undefined)
  })

  it('失败原样透传（由调用方决定降级文案）', async () => {
    const err = new Error('scheduler down')
    h.get.mockRejectedValueOnce(err)

    await expect(getSchedulerStatus()).rejects.toBe(err)
  })
})
