// web/src/api/__tests__/http.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// 捕获 http.ts 在模块加载时注册的响应错误拦截器，便于手动触发验证 401 逻辑
const { responseRejectedHandlers } = vi.hoisted(() => ({
  responseRejectedHandlers: [] as Array<(err: any) => any>,
}))

vi.mock('axios', () => {
  const instance = {
    interceptors: {
      request: { use: () => 0 },
      response: {
        use: (_fulfilled: any, rejected: any) => {
          if (rejected) responseRejectedHandlers.push(rejected)
          return 0
        },
      },
    },
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  }
  return {
    default: {
      create: vi.fn(() => instance),
      isCancel: vi.fn(() => false),
    },
  }
})

import { setUnauthorizedHandler } from '@/api/http'

describe('http 401 拦截器与 setUnauthorizedHandler', () => {
  beforeEach(() => {
    setUnauthorizedHandler(() => {})
    vi.clearAllMocks()
  })

  it('注册的 handler 在 401 时被调用', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(rejected({ response: { status: 401 }, config: {} })).rejects.toBeTruthy()
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('skipGlobalAuthRedirect: true 时 401 不触发 handler', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({ response: { status: 401 }, config: { skipGlobalAuthRedirect: true } }),
    ).rejects.toBeTruthy()
    expect(handler).not.toHaveBeenCalled()
  })

  it('AbortError 静默返回 null', async () => {
    const rejected = responseRejectedHandlers[0]
    const result = await rejected({ code: 'ERR_CANCELED', config: {} })
    expect(result).toBeNull()
  })
})
