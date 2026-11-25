// ForbiddenView（403 页）测试
//
// 契约：普通用户访问 admin-only 路由被 router.beforeEach 重定向到这里；
// 本页**不发任何后端请求**（避免二次 403），只渲染说明并给出「返回首页」出口。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import http from '@/api/http'
import ForbiddenView from './ForbiddenView.vue'

vi.mock('@/api/http', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))

async function mountView(locale: 'zh-CN' | 'en' = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/403', component: ForbiddenView },
    ],
  })
  await router.push('/403')
  await router.isReady()
  const wrapper = mount(ForbiddenView, {
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
    },
  })
  return { wrapper, router }
}

describe('ForbiddenView 403 页面', () => {
  beforeEach(() => vi.clearAllMocks())

  it('渲染 403 状态码与「无权限访问」说明', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.find('.code').text()).toBe('403')
    expect(wrapper.text()).toContain('无权限访问')
    expect(wrapper.text()).toContain('当前账号没有访问该页面的权限。')
  })

  it('挂载后不发起任何后端请求（避免二次 403）', async () => {
    await mountView()
    await flushPromises()
    expect(http.get).not.toHaveBeenCalled()
    expect(http.post).not.toHaveBeenCalled()
    expect(http.put).not.toHaveBeenCalled()
  })

  it('点击「返回首页」把路由切回 /', async () => {
    const { wrapper, router } = await mountView()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('返回首页'))
    expect(btn, '缺少返回首页按钮').toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('英文界面文案随之切换（确认走 i18n 而非硬编码）', async () => {
    const { wrapper } = await mountView('en')
    expect(wrapper.text()).toContain('Access denied')
    expect(wrapper.text()).toContain('Back to home')
    expect(wrapper.text()).not.toContain('无权限访问')
  })
})
