// web/src/api/__tests__/http.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// 捕获 http.ts 在模块加载时注册的响应错误拦截器与请求拦截器，便于手动触发验证
const { responseRejectedHandlers, requestHandlers } = vi.hoisted(() => ({
  responseRejectedHandlers: [] as Array<(err: any) => any>,
  requestHandlers: [] as Array<(config: any) => any>,
}))

vi.mock('axios', () => {
  const instance = {
    interceptors: {
      request: {
        use: (fulfilled: any) => {
          if (fulfilled) requestHandlers.push(fulfilled)
          return 0
        },
      },
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

import { setNetworkErrorNotifier, setUnauthorizedHandler } from '@/api/http'

describe('http 401 拦截器与 setUnauthorizedHandler', () => {
  beforeEach(() => {
    setUnauthorizedHandler(() => {})
    vi.clearAllMocks()
  })

  it('鉴权类 401（error 字段）触发 handler', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({ response: { status: 401, data: { error: '认证失败' } }, config: {} }),
    ).rejects.toBeTruthy()
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('鉴权类 401（会话已过期 detail）触发 handler', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({ response: { status: 401, data: { detail: '会话已过期，请重新登录' } }, config: {} }),
    ).rejects.toBeTruthy()
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('业务级 401（用户不存在）不触发全局 handler', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({ response: { status: 401, data: { detail: '用户不存在' } }, config: {} }),
    ).rejects.toBeTruthy()
    expect(handler).not.toHaveBeenCalled()
  })

  it('skipGlobalAuthRedirect: true 时鉴权 401 不触发 handler', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({
        response: { status: 401, data: { error: '认证失败' } },
        config: { skipGlobalAuthRedirect: true },
      }),
    ).rejects.toBeTruthy()
    expect(handler).not.toHaveBeenCalled()
  })

  it('AbortError 静默返回 null', async () => {
    const rejected = responseRejectedHandlers[0]
    const result = await rejected({ code: 'ERR_CANCELED', config: {} })
    expect(result).toBeNull()
  })
})

describe('http 响应拦截器：断网/超时提示与业务错误不弹窗（FIX-401）', () => {
  beforeEach(() => {
    setNetworkErrorNotifier(() => {})
    vi.clearAllMocks()
  })

  it('ERR_NETWORK 断网 → 提示"网络连接异常"并 reject', async () => {
    const notifier = vi.fn()
    setNetworkErrorNotifier(notifier)
    const rejected = responseRejectedHandlers[0]
    await expect(rejected({ code: 'ERR_NETWORK', message: 'Network Error', config: {} })).rejects.toBeTruthy()
    expect(notifier).toHaveBeenCalledWith('网络连接异常')
  })

  it('ECONNABORTED 超时 → 提示"请求超时"并 reject', async () => {
    const notifier = vi.fn()
    setNetworkErrorNotifier(notifier)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({ code: 'ECONNABORTED', message: 'timeout of 5000ms exceeded', config: {} }),
    ).rejects.toBeTruthy()
    expect(notifier).toHaveBeenCalledWith('请求超时')
  })

  it('业务错误（带响应体）→ 不弹任何提示，仅 reject', async () => {
    const notifier = vi.fn()
    setNetworkErrorNotifier(notifier)
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const rejected = responseRejectedHandlers[0]
    await expect(
      rejected({ response: { status: 500, data: { detail: '服务器内部错误' } }, config: {} }),
    ).rejects.toBeTruthy()
    expect(notifier).not.toHaveBeenCalled()
    expect(handler).not.toHaveBeenCalled()
  })

  it('无响应且非断网/超时（未知错误）→ 不弹提示，仅 reject', async () => {
    const notifier = vi.fn()
    setNetworkErrorNotifier(notifier)
    const rejected = responseRejectedHandlers[0]
    await expect(rejected({ code: 'ERR_BAD_OPTION', message: 'bad option', config: {} })).rejects.toBeTruthy()
    expect(notifier).not.toHaveBeenCalled()
  })
})

describe('http 请求拦截器：Cookie Token → Authorization 注入（FIX-401）', () => {
  // 清空 jsdom 中的全部 Cookie，避免用例间串扰
  function clearCookies(): void {
    document.cookie.split(';').forEach(c => {
      const name = c.split('=')[0].trim()
      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    })
  }

  beforeEach(() => {
    clearCookies()
    vi.clearAllMocks()
  })

  const runRequest = (config: any) => requestHandlers[0](config)

  it('Cookie 含 pilotstd_token 时注入 Authorization: Bearer 头', () => {
    document.cookie = 'pilotstd_token=eyJhbGciOiJIUzI1NiJ9; path=/'
    const cfg: any = { method: 'get', url: '/api/favorites/1', headers: {} }
    const result = runRequest(cfg)
    expect(result.headers.Authorization).toBe('Bearer eyJhbGciOiJIUzI1NiJ9')
  })

  it('Cookie 无 pilotstd_token 时不发送 Authorization 头', () => {
    const cfg: any = { method: 'get', url: '/api/favorites/1', headers: { Authorization: 'Bearer 旧值' } }
    runRequest(cfg)
    expect(cfg.headers.Authorization).toBeUndefined()
  })

  it('写请求保留 X-CSRF-Token 注入，同时携带 Authorization', () => {
    document.cookie = 'csrf_token=csrf123; path=/'
    document.cookie = 'pilotstd_token=jwt456; path=/'
    const cfg: any = { method: 'post', url: '/api/favorites', headers: {} }
    runRequest(cfg)
    expect(cfg.headers['X-CSRF-Token']).toBe('csrf123')
    expect(cfg.headers.Authorization).toBe('Bearer jwt456')
  })

  it('Cookie 解析异常时降级为空串，不中断请求', () => {
    // 覆盖 document.cookie 使其抛异常，验证 try-catch 兜底逻辑
    const desc = Object.getOwnPropertyDescriptor(document, 'cookie')
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      get: () => { throw new Error('模拟 Cookie 读取失败') },
      set: () => {},
    })
    try {
      const cfg: any = { method: 'get', url: '/api/x', headers: {} }
      const result = runRequest(cfg)
      expect(result.headers.Authorization).toBeUndefined()
    } finally {
      if (desc) Object.defineProperty(document, 'cookie', desc)
      else delete (document as any).cookie
    }
  })
})
