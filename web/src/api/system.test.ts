// api/system.test.ts — 系统资源监控（NEW-44）
//
// 契约：GET /system/resources，透传 options（routeTag）；**返回完整 AxiosResponse**
// （SystemResources 视图据 status 区分“资源不可用”，后端也会返回 error 字段）。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import { getSystemResources } from './system'

describe('system API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getSystemResources 走 GET /system/resources 并透传 routeTag', async () => {
    const response = {
      status: 200,
      data: { cpu: { percent: 10, count: 8 }, memory: { percent: 40 }, timestamp: 't' },
    }
    h.get.mockResolvedValueOnce(response)

    const result = await getSystemResources({ routeTag: '/resources' })

    expect(h.get).toHaveBeenCalledWith('/system/resources', { routeTag: '/resources' })
    expect(result).toBe(response)
  })

  it('后端资源不可用时 error 字段原样返回（不抛错，由视图渲染提示）', async () => {
    h.get.mockResolvedValueOnce({ status: 200, data: { error: 'psutil 不可用' } })

    const result = await getSystemResources()

    expect(result.data).toEqual({ error: 'psutil 不可用' })
    expect(h.get).toHaveBeenLastCalledWith('/system/resources', undefined)
  })

  it('失败原样透传', async () => {
    const err = new Error('resources 500')
    h.get.mockRejectedValueOnce(err)

    await expect(getSystemResources()).rejects.toBe(err)
  })
})
