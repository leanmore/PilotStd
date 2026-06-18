// web/src/api/http.ts — 共享 axios 实例 + 拦截器
import axios from 'axios'
import { useAppStore } from '../stores/app'

const http = axios.create({ baseURL: '/api', withCredentials: true })

// 请求拦截器：从 csrf_token Cookie 读取 CSRF 令牌
http.interceptors.request.use(config => {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  const token = match ? match[1] : ''
  if (token && config.method && config.method !== 'get') {
    config.headers['X-CSRF-Token'] = token
  }
  return config
})

// 响应拦截器：401 自动跳转登录
http.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      const store = useAppStore()
      store.loggedIn = false
      import('../router').then(m => m.default.push('/login'))
    }
    return Promise.reject(err)
  }
)

export default http
