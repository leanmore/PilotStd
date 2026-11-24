// api/quality.test.ts — 数据质量检查（NEW-44）
//
// 契约：POST /quality/run 把 payload **原样**作为 body 提交（不重组字段，后端按 schema 校验）；
// 返回**完整 AxiosResponse**（调用方据 status 判定是否已启动检查）。click 触发的动作接口，
// 不附 routeTag（走 globalPool）。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import { runQualityCheck } from './quality'

describe('quality API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('runQualityCheck 把 payload 原样作为 body 提交，不重组字段', async () => {
    const response = { status: 200, data: { ok: true, job_id: 'q-1' } }
    h.post.mockResolvedValueOnce(response)

    const result = await runQualityCheck({ scope: 'all', dry_run: true })

    expect(h.post).toHaveBeenCalledWith('/quality/run', { scope: 'all', dry_run: true })
    expect(result).toBe(response)
  })

  it('不传 payload 时 body 为 undefined（由后端使用默认检查项）', async () => {
    h.post.mockResolvedValueOnce({ status: 200, data: { ok: true } })

    await runQualityCheck()

    expect(h.post).toHaveBeenCalledWith('/quality/run', undefined)
  })

  it('失败原样抛出（不吞错、不伪造启动成功）', async () => {
    const err = new Error('quality busy')
    h.post.mockRejectedValueOnce(err)

    await expect(runQualityCheck()).rejects.toBe(err)
  })
})
