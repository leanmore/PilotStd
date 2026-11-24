// App.test.ts — 根组件挂载契约（NEW-44）
//
// App.vue 逻辑很薄，但两条“必须在 setup 同步完成”的副作用是硬约束：
//   1. useThemeSync() 同步调用 —— 首帧前注入主题 token，避免闪白/闪暗；
//   2. bindAppToast(useToast()) 同步调用 —— useToast 只能在 setup 上下文 inject；
//   3. onMounted 兜底拉偏好（幂等，可与 store 的 watch(loggedIn) 重复）。
// 另测模板分支：登录页不套 AppLayout，其余页面套 AppLayout，Toast 宿主始终存在。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const mocks = vi.hoisted(() => {
  const loadPreferences = vi.fn()
  return {
    themeSync: vi.fn(),
    useToast: vi.fn(),
    bindAppToast: vi.fn(),
    toast: { add: vi.fn(), removeGroup: vi.fn() },
    loadPreferences,
    store: { loadPreferences },
  }
})

vi.mock('@/composables/useThemeSync', () => ({ useThemeSync: mocks.themeSync }))
vi.mock('@/composables/useAppToast', () => ({ bindAppToast: mocks.bindAppToast }))
vi.mock('primevue/usetoast', () => ({ useToast: mocks.useToast }))
vi.mock('@/stores/app', () => ({ useAppStore: () => mocks.store }))
// 子组件直接打桩：App.vue 的契约是“挂哪个、包不包 Layout”，与子组件内部实现无关
vi.mock('@/components/AppLayout.vue', () => ({
  default: { name: 'AppLayout', template: '<div class="layout-stub"><slot /></div>' },
}))
vi.mock('@/components/ui/AppToast.vue', () => ({
  default: { name: 'AppToast', template: '<div class="toast-stub" />' },
}))

import App from './App.vue'

const Home = { name: 'Home', template: '<div class="page-home">home</div>' }
const Login = { name: 'Login', template: '<div class="page-login">login</div>' }
const Task = { name: 'Task', template: '<div class="page-task">task</div>' }

async function mountApp(path = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Home },
      { path: '/login', component: Login },
      { path: '/task', component: Task },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.useToast.mockReturnValue(mocks.toast)
})

describe('App.vue setup 副作用', () => {
  it('挂载即同步调用 useThemeSync 与 bindAppToast(useToast())（首帧前完成）', async () => {
    const { wrapper } = await mountApp()

    expect(mocks.useToast).toHaveBeenCalledTimes(1)
    expect(mocks.themeSync).toHaveBeenCalledTimes(1)
    // 必须把 useToast 返回的实例原样交给全局单例，不能传新对象/空壳
    expect(mocks.bindAppToast).toHaveBeenCalledWith(mocks.toast)

    wrapper.unmount()
  })

  it('onMounted 兜底调用 store.loadPreferences 一次', async () => {
    const { wrapper } = await mountApp()

    expect(mocks.loadPreferences).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('重复挂载各自执行一次，无模块级状态残留', async () => {
    const a = await mountApp()
    a.wrapper.unmount()
    const b = await mountApp()
    b.wrapper.unmount()

    expect(mocks.themeSync).toHaveBeenCalledTimes(2)
    expect(mocks.bindAppToast).toHaveBeenCalledTimes(2)
    expect(mocks.loadPreferences).toHaveBeenCalledTimes(2)
  })
})

describe('App.vue 模板分支', () => {
  it('非登录页：Toast 宿主 + AppLayout 包裹当前路由页面', async () => {
    const { wrapper } = await mountApp('/')

    expect(wrapper.find('.toast-stub').exists()).toBe(true)
    expect(wrapper.find('.layout-stub .page-home').exists()).toBe(true)

    wrapper.unmount()
  })

  it('登录页：不渲染 AppLayout，但 Toast 宿主仍在（登录页也能弹提示）', async () => {
    const { wrapper } = await mountApp('/login')

    expect(wrapper.find('.layout-stub').exists()).toBe(false)
    expect(wrapper.find('.page-login').exists()).toBe(true)
    expect(wrapper.find('.toast-stub').exists()).toBe(true)

    wrapper.unmount()
  })

  it('路由切换：登录 → 普通页出现 AppLayout，页面内容随 router-view 更新且不叠加', async () => {
    const { wrapper, router } = await mountApp('/login')
    expect(wrapper.find('.layout-stub').exists()).toBe(false)

    await router.push('/')
    await flushPromises()
    expect(wrapper.findAll('.layout-stub')).toHaveLength(1)
    expect(wrapper.find('.page-home').exists()).toBe(true)

    await router.push('/task')
    await flushPromises()
    expect(wrapper.findAll('.layout-stub')).toHaveLength(1)
    expect(wrapper.find('.page-task').exists()).toBe(true)
    expect(wrapper.find('.page-home').exists()).toBe(false)

    wrapper.unmount()
  })
})
