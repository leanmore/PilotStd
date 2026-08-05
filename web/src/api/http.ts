// web/src/api/http.ts — 共享 axios 实例 + 拦截器（CSRF / 401 降级 / AbortController）
import axios, { type AxiosError } from 'axios'
import { useAppStore } from '../stores/app'

const http = axios.create({ baseURL: '/api', withCredentials: true })

// ── 类型扩展：skipGlobalAuthRedirect ──
declare module 'axios' {
  interface AxiosRequestConfig {
    /** 设为 true 时，401 不触发全局登出跳转，由调用方自行降级 */
    skipGlobalAuthRedirect?: boolean
  }
  interface InternalAxiosRequestConfig {
    skipGlobalAuthRedirect?: boolean
  }
}

// AbortController 管理 — 每个请求独立 signal，路由切换时统一取消
let _reqId = 0
const pendingMap = new Map<string, AbortController>()

/** 取消所有 pending 请求（路由切换时调用）。 */
export function cancelAllRequests() {
  for (const [, controller] of pendingMap) {
    controller.abort()
  }
  pendingMap.clear()
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

// 请求拦截器：每次写请求实时读取最新 CSRF Token
http.interceptors.request.use(config => {
  const method = (config.method || '').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
  }
  // AbortController — 每次请求独立实例，用递增 id 防止 URL 碰撞
  const controller = new AbortController()
  const key = `${++_reqId}:${_reqKey(config)}`
  pendingMap.set(key, controller)
  config.signal = controller.signal
  ;(config as any).__abortKey = key
  return config
})

// 响应拦截器：清理 AbortController + 401 降级跳转（skipGlobalAuthRedirect 可跳过）
http.interceptors.response.use(
  r => {
    const key = (r.config as any).__abortKey
    if (key) pendingMap.delete(key)
    return r
  },
  (err: AxiosError) => {
    // AbortError → 静默忽略
    if (_isAbortError(err)) {
      const key = (err.config as any)?.__abortKey
      if (key) pendingMap.delete(key)
      return Promise.resolve(null)
    }
    const key = (err.config as any)?.__abortKey
    if (key) pendingMap.delete(key)
    // 仅核心接口的 401 触发全局登出，非核心接口由调用方自行降级
    if (err.response?.status === 401 && !err.config?.skipGlobalAuthRedirect) {
      const store = useAppStore()
      store.loggedIn = false
      import('../router').then(m => m.default.push('/login'))
    }
    return Promise.reject(err)
  },
)

export default http
