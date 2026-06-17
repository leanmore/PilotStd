import axios from 'axios'
import { useAppStore } from './stores/app'

const api = axios.create({ baseURL: '/api', withCredentials: true })

// 请求拦截器：从 csrf_token Cookie 读取 CSRF 令牌，写入 X-CSRF-Token 请求头
// 后端 AuthMiddleware 对 POST/PUT/DELETE/PATCH 校验此头
api.interceptors.request.use(config => {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  const token = match ? match[1] : ''
  if (token && config.method && config.method !== 'get') {
    config.headers['X-CSRF-Token'] = token
  }
  return config
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      const store = useAppStore()
      store.loggedIn = false
      // 使用 SPA 路由跳转，避免 window.location 全页重载导致焦点劫持
      import('./router').then(m => m.default.push('/login'))
    }
    return Promise.reject(err)
  }
)

export const login = (username: string, password: string) =>
  api.post('/login', new URLSearchParams({ username, password }))
export const getUsers = () => api.get('/users').then(r => r.data)
export const addUser = (username: string, password: string, role: string) =>
  api.post('/users', { username, password, role }).then(r => r.data)
export const deleteUser = (id: number) =>
  api.delete(`/users/${id}`).then(r => r.data)
export const changePassword = (oldPassword: string, newPassword: string) =>
  api.put('/users/password', { old_password: oldPassword, new_password: newPassword }).then(r => r.data)

export const getStats = () => api.get('/stats').then(r => r.data)
export const getFiles = (path: string) =>
  api.get('/files', { params: { path } }).then(r => r.data)
export const postQuery = (numbers: string[]) =>
  api.post('/query', { numbers }).then(r => r.data)
export const postDownload = (numbers: string[]) =>
  api.post('/download', { numbers }).then(r => r.data)
export const getAnnounceResults = () =>
  api.get('/announce/results').then(r => r.data)
export const postAnnounceCheck = (sinceDate?: string) =>
  api.post('/announce/check', null, { params: sinceDate ? { since_date: sinceDate } : {} }).then(r => r.data)
export const postCleanEmpty = (path: string) =>
  api.post('/clean-empty', null, { params: { path } }).then(r => r.data)
export const postNormalize = (items: any[]) =>
  api.post('/normalize', items).then(r => r.data)
export const postArchive = (items: any[], word_source_root?: string) =>
  api.post('/archive', { items, word_source_root }).then(r => r.data)
export const getSettings = () => api.get('/settings').then(r => r.data)
export const putSettings = (data: any) => api.put('/settings', data).then(r => r.data)
export const saveQueryResults = (results: any[]) =>
  api.post('/query/save', results).then(r => r.data)
export const getQueryResults = () =>
  api.get('/query/results').then(r => r.data)
export const getPendingItems = () =>
  api.get('/pending').then(r => r.data)
export const postScan = (path: string, recursive: boolean = true) =>
  api.post('/scan', new URLSearchParams({ path, recursive: String(recursive) })).then(r => r.data)
export const postRequery = (numbers: string[], site?: string) =>
  api.post('/pending/requery', numbers, { params: site ? { site } : {} }).then(r => r.data)
export const uploadFile = (file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload', fd).then(r => r.data)
}
