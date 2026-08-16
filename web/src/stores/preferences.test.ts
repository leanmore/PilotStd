// web/src/stores/preferences.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/http', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

import http from '@/api/http'
import { usePreferencesStore } from './preferences'

describe('usePreferencesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('getAll 用批量接口一次拉取全部偏好', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: { preferences: { ui: { theme: 'dark' }, task_path: '/x' } },
    })
    const store = usePreferencesStore()
    const all = await store.getAll()
    expect(http.get).toHaveBeenCalledWith('/user/preferences', { skipGlobalAuthRedirect: true })
    expect((all.ui as { theme: string }).theme).toBe('dark')
    expect(all.task_path).toBe('/x')
  })

  it('getDashboardLayout 读取 layout:dashboard 并透传 routeTag', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ data: { value: [{ i: 'stats' }] } })
    const store = usePreferencesStore()
    const layout = await store.getDashboardLayout('/')
    expect(http.get).toHaveBeenCalledWith('/user/preferences/layout:dashboard', { routeTag: '/' })
    expect(layout).toEqual([{ i: 'stats' }])
  })

  it('setDashboardLayout 写入 layout:dashboard 并返回成功', async () => {
    vi.mocked(http.put).mockResolvedValueOnce({})
    const store = usePreferencesStore()
    const ok = await store.setDashboardLayout([{ i: 'stats' }])
    expect(http.put).toHaveBeenCalledWith('/user/preferences/layout:dashboard', { value: [{ i: 'stats' }] })
    expect(ok).toBe(true)
  })

  it('setDashboardLayout 网络失败返回 false', async () => {
    vi.mocked(http.put).mockRejectedValueOnce(new Error('Network Error'))
    const store = usePreferencesStore()
    const ok = await store.setDashboardLayout([])
    expect(ok).toBe(false)
  })

  it('set 写入单个 key 并更新缓存', async () => {
    vi.mocked(http.put).mockResolvedValueOnce({})
    const store = usePreferencesStore()
    await store.set('sidebar_collapsed', true)
    expect(http.put).toHaveBeenCalledWith('/user/preferences/sidebar_collapsed', { value: true })
    expect(store.get('sidebar_collapsed')).toBe(true)
  })
})
