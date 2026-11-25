// registerHttpHandlers.test.ts — bootstrap 侧全局 HTTP 处理器注册（NEW-44）
//
// 本文件是 http.ts 与 stores/router/toast 之间的“解耦层”，测它就能锁住：
//   1. 两个处理器确实被注册（setUnauthorizedHandler / setNetworkErrorNotifier）；
//   2. 401 回调：非登录页 → clearUser() + push('/login')；已在登录页 → 完全空操作；
//   3. 断网回调：把拦截器文案转成 appToast.error({ summary })；
//   4. 回调在“调用时”才读 router/store（懒读取，注册时不依赖 Pinia 初始化）。
// 不测 http.ts 拦截器本身（已由 http.test.ts 覆盖）。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { App } from 'vue'

const h = vi.hoisted(() => ({
  route: { path: '/dashboard' },
  push: vi.fn(),
  clearUser: vi.fn(),
  toastError: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
  setNetworkErrorNotifier: vi.fn(),
  useAppStore: vi.fn(),
}))

vi.mock('@/api/http', () => ({
  setUnauthorizedHandler: h.setUnauthorizedHandler,
  setNetworkErrorNotifier: h.setNetworkErrorNotifier,
}))
vi.mock('@/stores/app', () => ({ useAppStore: h.useAppStore }))
vi.mock('@/composables/useAppToast', () => ({ appToast: { error: h.toastError } }))
vi.mock('@/router', () => ({
  default: { currentRoute: { value: h.route }, push: h.push },
}))

import { registerHttpHandlers } from './registerHttpHandlers'

/** 取注册进去的 401 处理器 / 断网提示器（每次注册应只调用一次 setter） */
const unauthorizedHandler = () => h.setUnauthorizedHandler.mock.calls[0][0] as () => void | Promise<void>
const networkNotifier = () => h.setNetworkErrorNotifier.mock.calls[0][0]

describe('registerHttpHandlers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.route.path = '/dashboard'
    h.useAppStore.mockReturnValue({ clearUser: h.clearUser })
    registerHttpHandlers({} as App)
  })

  it('注册 401 处理器与断网提示器各一次', () => {
    expect(h.setUnauthorizedHandler).toHaveBeenCalledTimes(1)
    expect(h.setNetworkErrorNotifier).toHaveBeenCalledTimes(1)
    expect(typeof unauthorizedHandler()).toBe('function')
    expect(typeof networkNotifier()).toBe('function')
  })

  it('注册阶段不依赖 store/router（懒读取，避免 Pinia 未就绪时崩溃）', () => {
    expect(h.useAppStore).not.toHaveBeenCalled()
    expect(h.push).not.toHaveBeenCalled()
  })

  it('401 处理器：非登录页 → 清空用户态并跳转 /login', async () => {
    h.route.path = '/settings'

    await unauthorizedHandler()()

    expect(h.useAppStore).toHaveBeenCalledTimes(1)
    expect(h.clearUser).toHaveBeenCalledTimes(1)
    expect(h.push).toHaveBeenCalledWith('/login')
  })

  it('401 处理器：已在 /login → 不重复跳转、不清空用户态', async () => {
    h.route.path = '/login'

    await unauthorizedHandler()()

    // 重复 push 会打断正在进行的重新登录
    expect(h.clearUser).not.toHaveBeenCalled()
    expect(h.push).not.toHaveBeenCalled()
  })

  it('401 处理器：注册后才改变路由，仍按调用时的当前路由判断', async () => {
    h.route.path = '/login'
    await unauthorizedHandler()()
    expect(h.push).not.toHaveBeenCalled()

    // 从登录页进入业务页后再触发 401，必须正常跳转
    h.route.path = '/task'
    await unauthorizedHandler()()
    expect(h.clearUser).toHaveBeenCalledTimes(1)
    expect(h.push).toHaveBeenCalledWith('/login')
  })

  it('断网提示器：把文案转成 appToast.error({ summary })', () => {
    networkNotifier()('网络连接失败，请检查网络')

    expect(h.toastError).toHaveBeenCalledTimes(1)
    expect(h.toastError).toHaveBeenCalledWith({ summary: '网络连接失败，请检查网络' })
  })

  it('断网提示器对超时文案同样原样透传', () => {
    networkNotifier()('请求超时，请稍后重试')

    expect(h.toastError).toHaveBeenCalledWith({ summary: '请求超时，请稍后重试' })
  })
})
