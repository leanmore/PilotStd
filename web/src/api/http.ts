// web/src/api/http.ts — 共享 axios 实例 + 拦截器（CSRF / 401 / AbortController）
import axios from 'axios'
import { useAppStore } from '../stores/app'

const http = axios.create({ baseURL: '/api', withCredentials: true })

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

// 请求拦截器：CSRF + AbortController signal
http.interceptors.request.use(config => {
  // CSRF
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  const token = match ? match[1] : ''
  if (token && config.method && config.method !== 'get') {
    config.headers['X-CSRF-Token'] = token
  }
  // AbortController — 每次请求独立实例，用递增 id 防止 URL 碰撞
  const controller = new AbortController()
  const key = `${++_reqId}:${_reqKey(config)}`
  pendingMap.set(key, controller)
  config.signal = controller.signal
  // 将 key 存入 config 供响应拦截器清理
  ;(config as any).__abortKey = key
  return config
})

// 响应拦截器：清理 AbortController + 401 跳转
http.interceptors.response.use(
  r => {
    const key = (r.config as any).__abortKey
    if (key) pendingMap.delete(key)
    return r
  },
  err => {
    // AbortError → 静默忽略，不触发调用方 error 回调
    if (_isAbortError(err)) {
      const key = (err.config as any)?.__abortKey
      if (key) pendingMap.delete(key)
      return Promise.resolve(null)
    }
    // 正常错误 → 清理 pending
    const key = (err.config as any)?.__abortKey
    if (key) pendingMap.delete(key)
    if (err.response?.status === 401) {
      const store = useAppStore()
      store.loggedIn = false
      import('../router').then(m => m.default.push('/login'))
    }
    return Promise.reject(err)
  },
)

export default http
