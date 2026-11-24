// api/backup.test.ts — 数据库备份管理 API（NEW-44）
//
// 契约：两个函数都返回**完整 AxiosResponse**（备份页要读 response.status / headers，
// 不能改成只取 .data）；getBackupList 透传 options（routeTag）；createBackup 是 click
// 触发的动作接口，不附 routeTag（走 globalPool，登出时可被 cancelAllRequests 清理）。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import { createBackup, getBackupList } from './backup'

describe('backup API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getBackupList 走 GET /backup/list，透传 routeTag，返回完整 AxiosResponse', async () => {
    const response = { status: 200, data: { items: [], count: 0 } }
    h.get.mockResolvedValueOnce(response)

    const result = await getBackupList({ routeTag: '/backup' })

    expect(h.get).toHaveBeenCalledWith('/backup/list', { routeTag: '/backup' })
    // 返回引用必须就是 AxiosResponse 本身：调用方会读 status
    expect(result).toBe(response)
  })

  it('getBackupList 无参数时 options 为 undefined（走全局降级池）', async () => {
    h.get.mockResolvedValueOnce({ status: 200, data: { items: [], count: 0 } })

    await getBackupList()

    expect(h.get).toHaveBeenCalledWith('/backup/list', undefined)
  })

  it('createBackup 走 POST /backup/create 且不附加 options', async () => {
    const response = { status: 200, data: { ok: true, message: '已创建' } }
    h.post.mockResolvedValueOnce(response)

    const result = await createBackup()

    expect(h.post).toHaveBeenCalledWith('/backup/create')
    expect(result).toBe(response)
  })

  it('请求失败原样透传（由调用方统一提示，不伪造成功）', async () => {
    const err = new Error('backup 500')
    h.get.mockRejectedValueOnce(err)

    await expect(getBackupList()).rejects.toBe(err)
  })
})
