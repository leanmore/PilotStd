import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import AppLayout from './AppLayout.vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

const Dummy = { template: '<div />' }
const routes = [
  { path: '/', component: { template: '<div>Home</div>' } },
  { path: '/task', component: Dummy },
  { path: '/organize', component: Dummy },
  { path: '/pending', component: Dummy },
  { path: '/announce', component: Dummy },
  { path: '/notification-logs', component: Dummy },
  { path: '/standards-status', component: Dummy },
  { path: '/settings', component: Dummy },
]

function mountLayout(locale: 'zh-CN' | 'en' = 'zh-CN') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  const router = createRouter({ history: createMemoryHistory(), routes })
  return mount(AppLayout, {
    global: {
      plugins: [pinia, i18n, router, PrimeVue, ToastService],
    },
    slots: { default: '<div class="test-content">测试内容</div>' },
  })
}

describe('AppLayout', () => {
  it('renders sidebar with nav items', () => {
    const wrapper = mountLayout()
    const items = wrapper.findAll('.nav-item')
    expect(items.length).toBeGreaterThanOrEqual(6)
  })

  it('renders slot content', () => {
    const wrapper = mountLayout()
    expect(wrapper.html()).toContain('测试内容')
  })

  it('切换语言到 en 后布局文案随之变化（i18n 生效）', () => {
    const zh = mountLayout('zh-CN')
    expect(zh.html()).toContain('设置')

    const english = mountLayout('en')
    expect(english.html()).toContain('Settings')
  })
})