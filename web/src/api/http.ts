// web/src/api/http.ts — 共享 axios 实例 + 拦截器（CSRF / 401 降级 / 路由级 AbortController）
import axios, { type AxiosError } from 'axios'
import type { RouteTag } from '../types/route-tag'

const http = axios.create({ baseURL: '/api', withCredentials: true })

// ── 类型扩展：skipGlobalAuthRedirect + routeTag ──
declare module 'axios' {
  interface AxiosRequestConfig {
    /** 设为 true 时，401 不触发全局登出跳转，由调用方自行降级 */
    skipGlobalAuthRedirect?: boolean
    /** 请求归属的路由标签（路由切换时精确取消；未迁移代码省略则走全局降级池） */
    routeTag?: RouteTag
  }
  interface InternalAxiosRequestConfig {
    skipGlobalAuthRedirect?: boolean
    routeTag?: RouteTag
  }
}

// AbortController 管理 — 路由级隔离：每个路由一个请求池，未迁移请求走全局降级池
let _reqId = 0
// 路由隔离池：routeTag → (reqKey → AbortController)
const pendingPools = new Map<string, Map<string, AbortController>>()
// 全局降级池：未带 routeTag 的请求（仅 cancelAllRequests 时取消，与重构前行为一致）
const globalPool = new Map<string, AbortController>()

/** 注册请求到对应池。routeTag 为空时进入全局降级池。 */
export function registerRequest(routeTag: string | undefined, reqKey: string, controller: AbortController): void {
  if (routeTag) {
    let pool = pendingPools.get(routeTag)
    if (!pool) {
      pool = new Map()
      pendingPools.set(routeTag, pool)
    }
    pool.set(reqKey, controller)
  } else {
    globalPool.set(reqKey, controller)
  }
}

/** 清理请求。池空时自动删除该路由的池，防止内存泄漏。 */
export function removeRequest(routeTag: string | undefined, reqKey: string): void {
  if (routeTag) {
    const pool = pendingPools.get(routeTag)
    if (pool) {
      pool.delete(reqKey)
      if (pool.size === 0) pendingPools.delete(routeTag)
    }
  } else {
    globalPool.delete(reqKey)
  }
}

/** 取消指定路由标签下的所有请求，随后删除该池（防内存泄漏）。 */
export function cancelByRouteTag(routeTag: string): void {
  const pool = pendingPools.get(routeTag)
  if (pool) {
    for (const controller of pool.values()) controller.abort()
    pendingPools.delete(routeTag)
  }
}

/** 取消所有请求（降级用途：登出、页面销毁等极端场景）。行为与重构前一致。 */
export function cancelAllRequests(): void {
  for (const pool of pendingPools.values()) {
    for (const controller of pool.values()) controller.abort()
  }
  pendingPools.clear()
  for (const controller of globalPool.values()) controller.abort()
  globalPool.clear()
}

/** 从 config 中衍生唯一请求 key，用于清理 pending 映射。 */
function _reqKey(c: { method?: string; url?: string }): string {
  return `${c.method || 'get'}:${c.url || ''}`
}

function _isAbortError(err: unknown): boolean {
  return !!(axios.isCancel(err) || (err as any)?.code === 'ERR_CANCELED' || (err as any)?.name === 'CanceledError')
}

/** 实时从 Cookie 读取 csrf_token，取最后一次匹配（避免同名 Cookie 旧值在前） */
function getCsrfToken(): string {
  const matches = document.cookie.matchAll(/(?:^|;\s*)csrf_token=([^;]*)/g);
  const lastMatch = [...matches].pop();
  return lastMatch ? decodeURIComponent(lastMatch[1]) : '';
}

// [FIX-401] 开始：实时从 Cookie 读取 pilotstd_token（会话令牌），供 Authorization 头注入
// 采用与 getCsrfToken 一致的原生 document.cookie 解析（js-cookie 非项目声明依赖，禁止引入）
function getSessionToken(): string {
  try {
    const matches = document.cookie.matchAll(/(?:^|;\s*)pilotstd_token=([^;]*)/g)
    const lastMatch = [...matches].pop()
    return lastMatch ? decodeURIComponent(lastMatch[1]) : ''
  } catch {
    // Cookie 解析异常时降级为空串，保证不中断请求
    return ''
  }
}
// [FIX-401] 结束

// 请求拦截器：每次写请求实时读取最新 CSRF Token + Cookie Token 注入 Authorization 头 + 注册 AbortController 到对应池
http.interceptors.request.use(config => {
  const method = (config.method || '').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
  }
  // [FIX-401] 开始：从 Cookie 读取 Token 并注入 Authorization 头（保留原有 X-CSRF-Token 传递逻辑）
  const token = getSessionToken()
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  } else {
    // Token 缺失时移除 Authorization 头，避免发送无效值
    delete config.headers['Authorization']
  }
  // [FIX-401] 结束
  // AbortController — 每次请求独立实例，用递增 id 防止 URL 碰撞
  const controller = new AbortController()
  const key = `${++_reqId}:${_reqKey(config)}`
  const routeTag = config.routeTag
  registerRequest(routeTag, key, controller)
  config.signal = controller.signal
  ;(config as any).__abortKey = key
  ;(config as any).__routeTag = routeTag
  return config
})

// 401 处理器（由 bootstrap 注册，避免 http.ts 静态依赖 stores/app 与 router 形成循环依赖）
type UnauthorizedHandler = () => void | Promise<void>
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler
}

// [FIX-401] 开始：断网/超时提示器（由 bootstrap 注册，避免 http.ts 静态依赖 UI 组件）
type NetworkErrorNotifier = (message: string) => void
let networkErrorNotifier: NetworkErrorNotifier | null = null

export function setNetworkErrorNotifier(notifier: NetworkErrorNotifier): void {
  networkErrorNotifier = notifier
}

/** 判定是否为鉴权类 401（Token 缺失/失效/会话过期）；业务级 401（如"用户不存在"）返回 false，不触发全局登出 */
function _isAuthExpired401(err: AxiosError): boolean {
  const data = (err.response as { data?: unknown } | undefined)?.data
  if (data && typeof data === 'object') {
    const body = data as { error?: unknown; detail?: unknown }
    if (typeof body.error === 'string') return true
    const detail = body.detail
    if (typeof detail === 'string') {
      return ['未登录', '认证失败', '会话已过期'].some(m => detail.includes(m))
    }
  }
  return false
}
// [FIX-401] 结束

// 响应拦截器：清理 AbortController + 断网/超时提示 + 鉴权 401 降级跳转（业务级 401 不跳转、不弹窗）
http.interceptors.response.use(
  r => {
    const cfg = r.config as any
    if (cfg?.__abortKey) removeRequest(cfg.__routeTag, cfg.__abortKey)
    return r
  },
  async (err: AxiosError) => {
    const cfg = err.config as any
    if (cfg?.__abortKey) removeRequest(cfg.__routeTag, cfg.__abortKey)
    // AbortError → 静默忽略（响应拦截器返回 null，调用方用 !r 检查识别取消）
    if (_isAbortError(err)) {
      return Promise.resolve(null)
    }
    // [FIX-401] 开始：真断网/超时 → 全局提示；业务错误不弹窗，仅 reject 交由业务层处理
    if (!err.response) {
      const code = err.code
      if (code === 'ERR_NETWORK') {
        networkErrorNotifier?.('网络连接异常')
      } else if (code === 'ECONNABORTED' || code === 'ETIMEDOUT' || (err.message || '').toLowerCase().includes('timeout')) {
        networkErrorNotifier?.('请求超时')
      }
    }
    // 仅鉴权类 401 触发全局登出；业务级 401（skipGlobalAuthRedirect 或非鉴权消息）由调用方自行降级
    if (_isAuthExpired401(err) && !err.config?.skipGlobalAuthRedirect && unauthorizedHandler) {
      await unauthorizedHandler()
    }
    // [FIX-401] 结束
    return Promise.reject(err)
  },
)

export default http
