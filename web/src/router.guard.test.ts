import { describe, it, expect, vi } from 'vitest'
import { hasRouteAccess, prepareRoute } from './router'

describe('hasRouteAccess', () => {
  it('admin 角色可访问 admin 路由', () => expect(hasRouteAccess('admin', 'admin')).toBe(true))
  it('普通用户不可访问 admin 路由', () => expect(hasRouteAccess('admin', 'user')).toBe(false))
  it('无 permission 的路由对所有角色开放', () => expect(hasRouteAccess(undefined, 'user')).toBe(true))
  it('permission=user 的路由对普通用户开放', () => expect(hasRouteAccess('user', 'user')).toBe(true))
})

describe('prepareRoute', () => {
  it('username 为空时先加载身份再判定（回归：admin 刷新后 quick action 消失）', async () => {
    const store = {
      username: '',
      role: 'user',
      loadPreferences: vi.fn(async () => { store.username = 'admin'; store.role = 'admin' }),
    }
    await expect(prepareRoute({ permission: 'admin' }, store)).resolves.toBe(true)
    expect(store.loadPreferences).toHaveBeenCalledTimes(1)
  })
  it('身份已加载时不再重复请求', async () => {
    const store = { username: 'u', role: 'user', loadPreferences: vi.fn() }
    await expect(prepareRoute({ permission: 'admin' }, store)).resolves.toBe(false)
    expect(store.loadPreferences).not.toHaveBeenCalled()
  })
})
