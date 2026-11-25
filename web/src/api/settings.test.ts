// settings.test.ts — 系统设置 / 统计 / 令牌 API 组装逻辑（NEW-44）
//
// 重点契约：
//   - 各只读端点路径与 routeTag 透传；
//   - 登录页背景图是公开接口（不带登录态参数，也不能误用 admin-only 的 /settings）；
//   - putSettings 提交部分配置，返回后端合并后的完整设置；
//   - getSettingsCached 的会话缓存 / 并发单飞 / 失败不缓存（finally 清空 loadingPromise）。
// sessionCache 是真实内存实现（无副作用），用 beforeEach 清空隔离用例。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Settings } from '../types/api'
import { sessionCache } from '@/utils/cache'

const h = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))

vi.mock('./http', () => ({ default: h }))

import {
  getLoginBackground,
  getSettings,
  getSettingsCached,
  getSettingsMetadata,
  getSettingsSchema,
  getStats,
  getToken,
  putSettings,
  refreshToken,
} from './settings'

const settings: Settings = {
  version: '0.55.33',
  storage: { scan_paths: ['D:/data'] },
  organize: {},
  scan: {},
  query: {},
  appearance: { login_bg: '/bg.png' },
}

describe('settings API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionCache.clear()
  })

  it('getSettings 走 GET /settings，透传 routeTag 并返回 data', async () => {
    h.get.mockResolvedValueOnce({ data: settings })

    const result = await getSettings('/settings')

    expect(h.get).toHaveBeenCalledWith('/settings', { routeTag: '/settings' })
    expect(result).toEqual(settings)
  })

  it('getLoginBackground 走公开的 GET /login-background（无参数）', async () => {
    h.get.mockResolvedValueOnce({ data: { url: '/bg.png' } })

    const result = await getLoginBackground()

    // 未登录页也能取背景图，不能改成需要登录态的 /settings
    expect(h.get).toHaveBeenCalledWith('/login-background')
    expect(result).toEqual({ url: '/bg.png' })
  })

  it('putSettings 走 PUT /settings，提交部分配置并返回合并结果', async () => {
    const patch = { appearance: { login_bg: '/new-bg.png' } }
    const merged = { ...settings, appearance: { login_bg: '/new-bg.png' } }
    h.put.mockResolvedValueOnce({ data: merged })

    const result = await putSettings(patch)

    expect(h.put).toHaveBeenCalledWith('/settings', patch)
    expect(result).toEqual(merged)
  })

  it('统计/结构/令牌/元数据只读端点的路径与 routeTag 透传', async () => {
    h.get.mockResolvedValue({ data: {} })

    await getStats('/settings')
    expect(h.get).toHaveBeenLastCalledWith('/stats', { routeTag: '/settings' })

    await getSettingsSchema()
    expect(h.get).toHaveBeenLastCalledWith('/settings/schema', { routeTag: undefined })

    await getToken('/settings')
    expect(h.get).toHaveBeenLastCalledWith('/settings/token', { routeTag: '/settings' })

    await getSettingsMetadata()
    expect(h.get).toHaveBeenLastCalledWith('/settings/metadata', { routeTag: undefined })
  })

  it('refreshToken 走 POST /settings/token/refresh，无请求体', async () => {
    const refreshed = { token: 'new-token', refreshed_at: '2026-11-24T12:00:00Z' }
    h.post.mockResolvedValueOnce({ data: refreshed })

    const result = await refreshToken()

    expect(h.post).toHaveBeenCalledWith('/settings/token/refresh')
    expect(result).toEqual(refreshed)
  })

  it('getSettingsCached 首次请求后写会话缓存，再次调用不发请求', async () => {
    h.get.mockResolvedValueOnce({ data: settings })

    const first = await getSettingsCached('/settings')
    const second = await getSettingsCached('/settings')

    expect(h.get).toHaveBeenCalledTimes(1)
    // 缓存返回同一引用，避免调用方拿到两份不同对象而误判变更
    expect(first).toBe(settings)
    expect(second).toBe(settings)
  })

  it('getSettingsCached 并发调用共享同一次请求（单飞）', async () => {
    // 手动控制 resolve 时机，确保第二个调用发生在首个请求结算之前
    const { promise, resolve } = Promise.withResolvers<{ data: Settings }>()
    h.get.mockReturnValueOnce(promise)

    const p1 = getSettingsCached()
    const p2 = getSettingsCached()
    expect(h.get).toHaveBeenCalledTimes(1)

    resolve({ data: settings })
    await expect(p1).resolves.toBe(settings)
    await expect(p2).resolves.toBe(settings)
    expect(h.get).toHaveBeenCalledTimes(1)
  })

  it('getSettingsCached 失败透传且不写缓存，下次调用重新请求', async () => {
    const err = new Error('settings 500')
    h.get.mockRejectedValueOnce(err)

    await expect(getSettingsCached()).rejects.toBe(err)
    // 失败的 promise 不能滞留：否则后续调用会永远复用已 rejected 的结果
    expect(sessionCache.get('settings')).toBeNull()

    h.get.mockResolvedValueOnce({ data: settings })
    await expect(getSettingsCached()).resolves.toBe(settings)
    expect(h.get).toHaveBeenCalledTimes(2)
  })
})
