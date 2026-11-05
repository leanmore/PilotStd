import { describe, it, expect } from 'vitest'
import { hasRouteAccess } from './router'

describe('hasRouteAccess', () => {
  it('admin 角色可访问 admin 路由', () => expect(hasRouteAccess('admin', 'admin')).toBe(true))
  it('普通用户不可访问 admin 路由', () => expect(hasRouteAccess('admin', 'user')).toBe(false))
  it('无 permission 的路由对所有角色开放', () => expect(hasRouteAccess(undefined, 'user')).toBe(true))
  it('permission=user 的路由对普通用户开放', () => expect(hasRouteAccess('user', 'user')).toBe(true))
})
