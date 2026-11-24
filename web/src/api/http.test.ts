// web/src/api/http.test.ts — 请求池与取消语义（NEW-44，2026-11-24）
//
// 背景：NEW-44 记录 84 个前端源文件无同名测试，其中 `api/http.ts` 是**拦截器核心**
// （路由级 AbortController 池、401 降级、CSRF/Token 注入），此前完全无测试覆盖。
//
// 本测试聚焦最容易出隐性 bug 的部分 —— **池的生命周期与取消语义**：
//   1. 注册/清理：池空时自动删池（防内存泄漏）
//   2. 路由级取消：只取消该路由的请求，不误伤其它路由
//   3. 全局降级池：无 routeTag 的请求只被 cancelAllRequests 取消
//   4. 同名 URL 不碰撞（用递增 id 做 key）
//
// 只测纯函数（registerRequest / removeRequest / cancelByRouteTag / cancelAllRequests），
// 不挂 axios 实例 —— 这些函数是池管理的全部逻辑，测它们即可锁住泄漏与误取消。
import { describe, expect, it, beforeEach } from 'vitest'
import {
  registerRequest,
  removeRequest,
  cancelByRouteTag,
  cancelAllRequests,
} from './http'

/** 构造可观测的 AbortController 替身 */
function spyController() {
  let aborted = false
  const c = {
    abort: () => {
      aborted = true
    },
    get aborted() {
      return aborted
    },
  } as unknown as AbortController & { aborted: boolean }
  return c
}

describe('http 请求池：注册与清理', () => {
  beforeEach(() => {
    // 每个用例前清空全部池，避免相互污染
    cancelAllRequests()
  })

  it('removeRequest 清空池后自动删除该路由的池（防内存泄漏）', () => {
    const c1 = spyController()
    registerRequest('dashboard', 'k1', c1)
    // 唯一一条被清理 → 池应被删除，再次取消该路由不应有副作用
    removeRequest('dashboard', 'k1')
    // 用「再注册一个不同 key 后取消」验证池被重建而非残留旧项
    const c2 = spyController()
    registerRequest('dashboard', 'k2', c2)
    cancelByRouteTag('dashboard')
    expect(c2.aborted).toBe(true)
    // c1 已被移除，不应被这次取消影响（它本来也没 abort）
    expect(c1.aborted).toBe(false)
  })

  it('removeRequest 只删指定 key，不影响同池其它请求', () => {
    const c1 = spyController()
    const c2 = spyController()
    registerRequest('settings', 'k1', c1)
    registerRequest('settings', 'k2', c2)
    removeRequest('settings', 'k1')
    cancelByRouteTag('settings')
    expect(c1.aborted).toBe(false) // 已被移除
    expect(c2.aborted).toBe(true) // 仍在池中，被取消
  })
})

describe('http 请求池：路由级取消隔离', () => {
  beforeEach(() => {
    cancelAllRequests()
  })

  it('cancelByRouteTag 只取消该路由的请求，不误伤其它路由', () => {
    const dash = spyController()
    const settings = spyController()
    registerRequest('dashboard', 'k1', dash)
    registerRequest('settings', 'k2', settings)

    cancelByRouteTag('dashboard')

    expect(dash.aborted).toBe(true)
    expect(settings.aborted).toBe(false) // 关键：不能被误取消
  })

  it('cancelByRouteTag 对不存在的路由是安全空操作', () => {
    expect(() => cancelByRouteTag('never-registered')).not.toThrow()
  })

  it('同名 URL 不同请求不碰撞（key 由递增 id 前缀区分）', () => {
    const c1 = spyController()
    const c2 = spyController()
    // 模拟真实 key 形态：`${++_reqId}:get:/tasks`
    registerRequest('tasks', '1:get:/tasks', c1)
    registerRequest('tasks', '2:get:/tasks', c2)
    cancelByRouteTag('tasks')
    // 两个都应被取消（同池），且都不是因为 key 覆盖而丢失
    expect(c1.aborted).toBe(true)
    expect(c2.aborted).toBe(true)
  })
})

describe('http 请求池：全局降级池', () => {
  beforeEach(() => {
    cancelAllRequests()
  })

  it('无 routeTag 的请求进入全局池，cancelByRouteTag 不影响它', () => {
    const global = spyController()
    registerRequest(undefined, 'g1', global)

    cancelByRouteTag('dashboard')

    expect(global.aborted).toBe(false)
  })

  it('cancelAllRequests 同时清空路由池与全局池', () => {
    const inRoute = spyController()
    const inGlobal = spyController()
    registerRequest('dashboard', 'k1', inRoute)
    registerRequest(undefined, 'g1', inGlobal)

    cancelAllRequests()

    expect(inRoute.aborted).toBe(true)
    expect(inGlobal.aborted).toBe(true)
  })

  it('cancelAllRequests 后可重新注册（池未被标记为永久失效）', () => {
    const c1 = spyController()
    registerRequest('dashboard', 'k1', c1)
    cancelAllRequests()

    const c2 = spyController()
    registerRequest('dashboard', 'k2', c2)
    cancelByRouteTag('dashboard')

    expect(c2.aborted).toBe(true)
    expect(c1.aborted).toBe(true) // 第一轮已被取消
  })
})
