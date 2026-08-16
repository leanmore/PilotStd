// web/src/stores/app-auth.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/http', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}))

vi.mock('@/composables/useUserPreferences', () => ({
  useUserPreferences: () => ({
    theme: { value: 'light' },
    locale: { value: 'zh-CN' },
    taskPath: { value: '/inbox' },
    quietHours: { value: { enabled: false } },
    loadFromBackend: vi.fn().mockResolvedValue(undefined),
    cleanupLegacy: vi.fn(),
  }),
}))

import http from '@/api/http'
import { useAppStore } from './app'

describe('useAppStore 认证', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('clearUser 清空全部用户状态', () => {
    const store = useAppStore()
    store.loggedIn = true
    store.userId = 1
    store.username = 'admin'
    store.role = 'admin'
    store.dashboardLocked = false
    store.clearUser()
    expect(store.loggedIn).toBe(false)
    expect(store.userId).toBe(0)
    expect(store.username).toBe('')
    expect(store.role).toBe('user')
    expect(store.dashboardLocked).toBe(true)
  })

  it('loadPreferences 用 http 实例拉取 auth/me 并恢复身份', async () => {
    vi.mocked(http.get).mockResolvedValue({ data: { id: 1, role: 'admin', username: 'superadmin' } })
    const store = useAppStore()
    store.loggedIn = true
    await store.loadPreferences()
    expect(http.get).toHaveBeenCalledWith('/auth/me')
    expect(store.userId).toBe(1)
    expect(store.role).toBe('admin')
    expect(store.username).toBe('superadmin')
  })
})
