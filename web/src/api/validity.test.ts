// api/validity.test.ts — 时效性检查 API + HH:MM 解析/格式化（NEW-44）
//
// 契约：配置读写 / 触发检查 / 历史分页 / 入队；parseExecuteTime 对空值与非法值容错为 0
// 并把越界值夹到合法区间（小时 0~23、分钟 0~59）；formatExecuteTime 恒两位前导零。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))

vi.mock('./http', () => ({ default: h }))

import {
  enqueueValidityCheck,
  formatExecuteTime,
  getValidityConfig,
  getValidityHistory,
  parseExecuteTime,
  putValidityConfig,
  runValidityCheck,
} from './validity'

describe('validity API：请求组装', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getValidityConfig 走 GET /validity/config 并透传 routeTag', async () => {
    const config = { first_weekday: 1, execute_time: '02:00', total_weeks: 4, frequency_weeks: 1, batch_size: 20, batch_interval: 5, check_ratio: 100 }
    h.get.mockResolvedValueOnce({ data: config })

    await expect(getValidityConfig('/validity')).resolves.toEqual(config)
    expect(h.get).toHaveBeenCalledWith('/validity/config', { routeTag: '/validity' })
  })

  it('putValidityConfig 只提交变更字段（部分更新语义）', async () => {
    h.put.mockResolvedValueOnce({ data: { ok: true, message: 'saved' } })

    const result = await putValidityConfig({ batch_size: 50 })

    expect(h.put).toHaveBeenCalledWith('/validity/config', { batch_size: 50 })
    expect(result.ok).toBe(true)
  })

  it('runValidityCheck 无体 POST；enqueueValidityCheck body 用 file_paths 字段', async () => {
    h.post.mockResolvedValue({ data: { ok: true, checked: 0, changed: 0 } })

    await runValidityCheck()
    expect(h.post).toHaveBeenLastCalledWith('/validity/run')

    h.post.mockResolvedValueOnce({ data: { ok: true, enqueued: 2, total: 2 } })
    await enqueueValidityCheck(['D:/a.pdf', 'D:/b.pdf'])
    expect(h.post).toHaveBeenLastCalledWith('/validity/enqueue', {
      file_paths: ['D:/a.pdf', 'D:/b.pdf'],
    })
  })

  it('getValidityHistory 透传分页 params 与 routeTag', async () => {
    const payload = { total: 0, page: 2, page_size: 10, items: [] }
    h.get.mockResolvedValueOnce({ data: payload })

    await expect(getValidityHistory({ page: 2, page_size: 10 }, '/validity')).resolves.toEqual(payload)
    expect(h.get).toHaveBeenCalledWith('/validity/history', {
      params: { page: 2, page_size: 10 },
      routeTag: '/validity',
    })
  })

  it('失败原样透传', async () => {
    const err = new Error('validity 500')
    h.post.mockRejectedValueOnce(err)
    await expect(runValidityCheck()).rejects.toBe(err)
  })
})

describe('validity 时间工具：parseExecuteTime', () => {
  it('合法 HH:MM 原样解析（含单个数字小时）', () => {
    expect(parseExecuteTime('09:30')).toEqual({ hour: 9, minute: 30 })
    expect(parseExecuteTime('9:05')).toEqual({ hour: 9, minute: 5 })
  })

  it('空值 / 非法值容错为 0，不抛错', () => {
    expect(parseExecuteTime(undefined)).toEqual({ hour: 0, minute: 0 })
    expect(parseExecuteTime(null)).toEqual({ hour: 0, minute: 0 })
    expect(parseExecuteTime('')).toEqual({ hour: 0, minute: 0 })
    expect(parseExecuteTime('abc')).toEqual({ hour: 0, minute: 0 })
    // 只有一段时分钟缺失 → 0
    expect(parseExecuteTime('08')).toEqual({ hour: 8, minute: 0 })
  })

  it('越界值夹到合法区间（避免传给后端非法时间）', () => {
    expect(parseExecuteTime('25:70')).toEqual({ hour: 23, minute: 59 })
    expect(parseExecuteTime('-3:-9')).toEqual({ hour: 0, minute: 0 })
  })
})

describe('validity 时间工具：formatExecuteTime', () => {
  it('恒输出两位前导零', () => {
    expect(formatExecuteTime(9, 5)).toBe('09:05')
    expect(formatExecuteTime(0, 0)).toBe('00:00')
    expect(formatExecuteTime(23, 59)).toBe('23:59')
  })

  it('与 parseExecuteTime 往返一致（设置面板回显依赖）', () => {
    const { hour, minute } = parseExecuteTime('07:45')
    expect(formatExecuteTime(hour, minute)).toBe('07:45')
  })
})
