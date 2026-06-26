import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import AppLayout from './AppLayout.vue'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'

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

function mountLayout() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({ history: createMemoryHistory(), routes })
  return mount(AppLayout, {
    global: {
      plugins: [pinia, i18n, router, PrimeVue],
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
})
