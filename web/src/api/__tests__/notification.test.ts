// api/__tests__/notification.test.ts — 通知 API 函数单元测试
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock http 模块，验证 API 函数正确调用 axios
const mockGet = vi.fn()
const mockPut = vi.fn()
const mockPost = vi.fn()

vi.mock('../http', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    put: (...args: any[]) => mockPut(...args),
    post: (...args: any[]) => mockPost(...args),
  },
}))

import {
  getNotificationConfig,
  putNotificationConfig,
  testNotification,
  getNotificationLogs,
  markNotificationRead,
} from '../notification'

describe('notification API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getNotificationConfig 调用 GET /notification/config 并返回 data', async () => {
    const mockConfig = { enabled: true, channels: {}, rules: {} }
    mockGet.mockResolvedValue({ data: mockConfig })

    const result = await getNotificationConfig()

    expect(mockGet).toHaveBeenCalledWith('/notification/config', { routeTag: undefined })
    expect(result).toEqual(mockConfig)
  })

  it('putNotificationConfig 调用 PUT /notification/config 并传部分配置', async () => {
    mockPut.mockResolvedValue({ data: { ok: true } })
    const partial = { enabled: false }

    const result = await putNotificationConfig(partial)

    expect(mockPut).toHaveBeenCalledWith('/notification/config', partial)
    expect(result.ok).toBe(true)
  })

  it('testNotification 调用 POST /notification/test 并附渠道参数', async () => {
    mockPost.mockResolvedValue({ data: { ok: true } })

    const result = await testNotification('telegram', { bot_token: 'tk', chat_id: '123' })

    expect(mockPost).toHaveBeenCalledWith('/notification/test', {
      channel: 'telegram',
      params: { bot_token: 'tk', chat_id: '123' },
    })
    expect(result.ok).toBe(true)
  })

  it('testNotification 处理失败返回 error 字段', async () => {
    mockPost.mockResolvedValue({ data: { ok: false, error: 'token无效' } })

    const result = await testNotification('wechat', {})

    expect(result.ok).toBe(false)
    expect(result.error).toBe('token无效')
  })

  it('getNotificationLogs 传递分页与筛选参数', async () => {
    mockGet.mockResolvedValue({ data: { total: 0, page: 1, page_size: 20, items: [] } })

    const result = await getNotificationLogs({ page: 2, channel: 'email', is_read: false })

    expect(mockGet).toHaveBeenCalledWith('/notification/logs', {
      params: { page: 2, channel: 'email', is_read: false },
    })
    expect(result.total).toBe(0)
  })

  it('markNotificationRead 传 id 标记单条，不传则标记全部', async () => {
    mockPost.mockResolvedValue({ data: { ok: true, message: 'done' } })

    // 传 id
    await markNotificationRead(42)
    expect(mockPost).toHaveBeenCalledWith('/notification/read', { id: 42 })

    // 不传 id → null
    await markNotificationRead(null)
    expect(mockPost).toHaveBeenCalledWith('/notification/read', { id: null })

    // undefined → null
    await markNotificationRead()
    expect(mockPost).toHaveBeenCalledWith('/notification/read', { id: null })
  })
})
