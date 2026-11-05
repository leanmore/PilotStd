// web/src/api/http.ts — 共享 axios 实例 + 拦截器（CSRF / 401 降级 / 路由级 AbortController）
import axios, { type AxiosError } from 'axios'
import type { RouteTag } from '../types/route-tag'
import { i18n } from '@/i18n'

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
  // 记录请求发出时间：登录/登出后用于识别“旧请求的 401”，避免覆盖重新登录
  ;(config as unknown as { __issuedAt?: number }).__issuedAt = Date.now()
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

// 登录/登出时间戳：早于它发出的请求，即使返回 401 也不得再触发全局登出（避免覆盖刚完成的重新登录）
let lastAuthAt = 0

/** 登录成功/登出时调用：让旧的在途请求失效，不再触发全局 401 跳转。 */
export function notifyAuthChanged(): void {
  lastAuthAt = Date.now()
}

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
  // 先看状态码：403 的 `{"error":"..."}` 不是会话失效，绝不能触发全局登出
  if (err.response?.status !== 401) return false
  const data = (err.response as { data?: unknown } | undefined)?.data
  if (data && typeof data === 'object') {
    const body = data as { error?: unknown; detail?: unknown }
    if (typeof body.error === 'string') return true
    const detail = body.detail
    if (typeof detail === 'string') {
      // i18n-allow: 匹配后端返回的中文错误文案（判定会话失效），翻译即失效
      return ['未登录', '认证失败', '会话已过期'].some(m => detail.includes(m))
    }
  }
  return false
}

/** 从后端错误体提取用户可读文案：message_key 优先走 i18n，其次 detail/error。 */
function _apiMessage(data: unknown): string {
  if (!data || typeof data !== 'object') return ''
  const body = data as { message_key?: unknown; params?: unknown; detail?: unknown; error?: unknown }
  if (typeof body.message_key === 'string' && body.message_key) {
    try {
      return i18n.global.t(body.message_key, (body.params as Record<string, unknown>) || {})
    } catch {
      return body.message_key
    }
  }
  if (typeof body.detail === 'string' && body.detail) return body.detail
  if (typeof body.error === 'string' && body.error) return body.error
  return ''
}

/** 供业务层取错误文案（优先拦截器归一化结果，其次兜底通用文案）。 */
export function getApiErrorMessage(err: unknown): string {
  const anyErr = err as { userMessage?: string; response?: { status?: number } } | undefined
  if (anyErr?.userMessage) return anyErr.userMessage
  const status = anyErr?.response?.status
  if (status === 403) return i18n.global.t('http.forbidden')
  return i18n.global.t('http.api_error', { message: i18n.global.t('http.network_error') })
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
        networkErrorNotifier?.(i18n.global.t('http.network_error'))
      } else if (code === 'ECONNABORTED' || code === 'ETIMEDOUT' || (err.message || '').toLowerCase().includes('timeout')) {
        networkErrorNotifier?.(i18n.global.t('http.timeout'))
      }
    }
    // 统一错误契约：403/400/422/500 都把可读文案挂到 err.userMessage，供业务层直接展示
    const message = _apiMessage(err.response?.data)
    if (message) {
      ;(err as unknown as { userMessage?: string }).userMessage = message
    }
    // 仅鉴权类 401 触发全局登出；登录/身份接口与“登录前发出的旧请求”必须豁免，
    // 否则重新登录瞬间的并发 401 会再次把用户踢回 /login（2026-11-05 E2E 实测）。
    const cfgUrl = String(err.config?.url || "")
    const isAuthEndpoint = /\/auth\/me|\/login\//.test(cfgUrl) || cfgUrl.endsWith("/login")
    const issuedAt = Number((err.config as unknown as { __issuedAt?: number })?.__issuedAt || 0)
    const staleRequest = issuedAt > 0 && issuedAt < lastAuthAt
    if (_isAuthExpired401(err) && !err.config?.skipGlobalAuthRedirect && unauthorizedHandler
        && !isAuthEndpoint && !staleRequest) {
      await unauthorizedHandler()
    }
    // [FIX-401] 结束
    return Promise.reject(err)
  },
)

export default http
