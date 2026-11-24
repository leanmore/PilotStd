// RegisterView 测试
//
// 契约：客户端必填校验先于请求；注册成功即视为登录态并跳 `/`；
// 后端错误按「detail 字符串 > 409 已存在 > 429 限流 > 403 关闭 > 兜底」优先级映射文案。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { register } from '@/api/auth'
import RegisterView from './RegisterView.vue'

vi.mock('@/api/auth', () => ({ register: vi.fn() }))

const Blank = { template: '<div />' }

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Blank },
      { path: '/login', component: Blank },
      { path: '/register', component: RegisterView },
    ],
  })
  await router.push('/register')
  await router.isReady()
  const wrapper = mount(RegisterView, {
    global: {
      plugins: [PrimeVue, router, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  return { wrapper, router }
}

/** 让后端以某个 HTTP 错误拒绝注册 */
function httpError(status: number, data: Record<string, unknown> = {}) {
  return Object.assign(new Error(`http ${status}`), { response: { status, data } })
}

describe('RegisterView 注册表单', () => {
  beforeEach(() => vi.clearAllMocks())

  it('用户名或密码为空时只做前端校验，不发注册请求', async () => {
    const { wrapper } = await mountView()
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('请填写用户名和密码')
    expect(register).not.toHaveBeenCalled()
  })

  it('填写完整后提交：register 收到 username/password，成功后跳转首页', async () => {
    vi.mocked(register).mockResolvedValue({ ok: true } as never)
    const { wrapper, router } = await mountView()
    await wrapper.find('input[name="username"]').setValue('alice')
    await wrapper.find('input[name="password"]').setValue('secret123')
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(register).toHaveBeenCalledWith('alice', 'secret123')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('在密码框回车等同点击注册按钮', async () => {
    vi.mocked(register).mockResolvedValue({ ok: true } as never)
    const { wrapper } = await mountView()
    await wrapper.find('input[name="username"]').setValue('bob')
    await wrapper.find('input[name="password"]').setValue('secret123')
    await wrapper.find('input[name="password"]').trigger('keyup.enter')
    await flushPromises()
    expect(register).toHaveBeenCalledTimes(1)
  })

  it('409 映射为「用户名已存在」，403 映射为「注册功能未开放」', async () => {
    const conflict = await mountView()
    vi.mocked(register).mockRejectedValueOnce(httpError(409))
    await conflict.wrapper.find('input[name="username"]').setValue('alice')
    await conflict.wrapper.find('input[name="password"]').setValue('secret123')
    await conflict.wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(conflict.wrapper.text()).toContain('用户名已存在')

    const disabled = await mountView()
    vi.mocked(register).mockRejectedValueOnce(httpError(403))
    await disabled.wrapper.find('input[name="username"]').setValue('alice')
    await disabled.wrapper.find('input[name="password"]').setValue('secret123')
    await disabled.wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(disabled.wrapper.text()).toContain('注册功能未开放')
  })

  it('后端 detail 字符串优先于状态码文案', async () => {
    vi.mocked(register).mockRejectedValue(httpError(400, { detail: '账号已被锁定，请联系管理员' }))
    const { wrapper } = await mountView()
    await wrapper.find('input[name="username"]').setValue('alice')
    await wrapper.find('input[name="password"]').setValue('secret123')
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('账号已被锁定，请联系管理员')
    expect(wrapper.text()).not.toContain('注册失败，请重试')
  })

  it('无 response 的网络异常降级为「注册失败，请重试」且按钮恢复可点', async () => {
    vi.mocked(register).mockRejectedValue(new Error('Network Error'))
    const { wrapper } = await mountView()
    await wrapper.find('input[name="username"]').setValue('alice')
    await wrapper.find('input[name="password"]').setValue('secret123')
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('注册失败，请重试')
    expect(wrapper.findAll('button')[0].attributes('disabled')).toBeUndefined()
  })
})
