import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import LoginView from './LoginView.vue'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

vi.mock('@/api', () => ({
  login: vi.fn(),
  getLoginBackground: vi.fn(),
}))

import { getLoginBackground } from '@/api'

// 可控的 Image 桩：jsdom 不执行真实图片加载，通过捕获实例手动触发 onload/onerror
let lastImage: { onload: (() => void) | null; onerror: (() => void) | null; src: string } | null = null
class FakeImage {
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  src = ''
  constructor() {
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- 测试桩需捕获实例以手动触发 onload/onerror
    lastImage = this
  }
}

const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

/** 用真实 locale 文件挂载（空 messages 会让 t() 回显 key，断言即失去意义） */
function makeI18n(locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

function mountLogin(locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN') {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/login', component: LoginView }, { path: '/', component: { template: '<div>Home</div>' } }],
  })
  return mount(LoginView, {
    global: { plugins: [createPinia(), router, PrimeVue, makeI18n(locale)] },
  })
}

function bgStyle(wrapper: ReturnType<typeof mountLogin>) {
  return wrapper.find('.login-page').attributes('style') || ''
}

beforeEach(() => {
  lastImage = null
  vi.mocked(getLoginBackground).mockReset()
  vi.mocked(getLoginBackground).mockResolvedValue({ url: '' })
})

afterEach(() => {
  vi.unstubAllGlobals()
  warnSpy.mockClear()
})

describe('LoginView', () => {
  it('renders password input', () => {
    const wrapper = mountLogin()
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('renders login button', () => {
    const wrapper = mountLogin()
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text().replace(/\s/g, '')).toContain('登录')
  })

  it('renders PilotStd title', () => {
    const wrapper = mountLogin()
    expect(wrapper.find('h1').text()).toBe('PilotStd')
  })

  // 批 6 i18n 守卫：文案确实来自 locales（源文案带空格，故用 login.submit_spaced），且随语言切换而变化
  it('文案随语言切换（zh-CN / en）', () => {
    const zh = mountLogin('zh-CN')
    expect(zh.find('button').text().replace(/\s/g, '')).toContain('登录')
    expect(zh.html()).toContain('密码')

    const english = mountLogin('en')
    // en 源文案 "Log In"（去空格后 LogIn），故大小写不敏感比对
    expect(english.find('button').text().replace(/\s/g, '').toLowerCase()).toContain('login')
    expect(english.html()).not.toContain('login.submit_spaced')
  })
})

describe('LoginView 背景图两阶段加载', () => {
  it('组件创建即请求公开背景图接口（不等待 onMounted / 登录态）', () => {
    mountLogin()
    expect(getLoginBackground).toHaveBeenCalledTimes(1)
  })

  it('阶段2：URL 返回后 new Image() 预加载，onload 后才应用 background-image', async () => {
    vi.mocked(getLoginBackground).mockResolvedValue({ url: '/api/backgrounds/abc.png' })
    vi.stubGlobal('Image', FakeImage)
    const wrapper = mountLogin()

    await flushPromises()
    // 已创建 Image 预加载实例，但 onload 未触发前不应用背景
    expect(lastImage).not.toBeNull()
    expect(lastImage!.src).toBe('/api/backgrounds/abc.png')
    expect(bgStyle(wrapper)).not.toContain('/api/backgrounds/abc.png')

    lastImage!.onload!()
    await nextTick()
    expect(bgStyle(wrapper)).toContain('background-image: url("/api/backgrounds/abc.png")')
  })

  it('API 失败 → 降级为默认渐变，不设置背景图且无未捕获异常', async () => {
    vi.mocked(getLoginBackground).mockRejectedValue(new Error('network down'))
    const wrapper = mountLogin()
    await flushPromises()
    expect(bgStyle(wrapper)).toBe('')
    expect(warnSpy).toHaveBeenCalled()
  })

  it('图片加载失败（onerror）→ 降级为默认渐变', async () => {
    vi.mocked(getLoginBackground).mockResolvedValue({ url: '/api/backgrounds/broken.png' })
    vi.stubGlobal('Image', FakeImage)
    const wrapper = mountLogin()
    await flushPromises()

    lastImage!.onerror!()
    await nextTick()
    expect(bgStyle(wrapper)).toBe('')
    expect(warnSpy).toHaveBeenCalled()
  })

  it('file:// 本地路径（桌面端遗留值）→ 跳过预加载，使用默认渐变', async () => {
    vi.mocked(getLoginBackground).mockResolvedValue({ url: 'file:///C:/pilotstd/bg.png' })
    vi.stubGlobal('Image', FakeImage)
    const wrapper = mountLogin()
    await flushPromises()
    expect(lastImage).toBeNull()
    expect(bgStyle(wrapper)).toBe('')
  })

  it('URL 为空串（未配置背景图）→ 不创建 Image、不设背景，走默认渐变兜底而非空白', async () => {
    vi.mocked(getLoginBackground).mockResolvedValue({ url: '' })
    vi.stubGlobal('Image', FakeImage)
    const wrapper = mountLogin()
    await flushPromises()
    expect(getLoginBackground).toHaveBeenCalledTimes(1)
    expect(lastImage).toBeNull()
    expect(bgStyle(wrapper)).toBe('')
  })
})
