import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import AppLayout from './AppLayout.vue'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'

function mountLayout() {
  setActivePinia(createPinia())
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: { template: '<div>Home</div>' } }],
  })
  return mount(AppLayout, {
    global: {
      plugins: [createPinia(), i18n, router, PrimeVue],
    },
    slots: { default: '<div class="test-content">测试内容</div>' },
  })
}

describe('AppLayout', () => {
  it('renders sidebar with nav items', () => {
    // Mock desktop: innerWidth >= 1024 (jsdom default)
    const wrapper = mountLayout()
    const items = wrapper.findAll('.nav-item')
    expect(items.length).toBeGreaterThanOrEqual(6)
  })

  it('renders slot content', () => {
    const wrapper = mountLayout()
    expect(wrapper.html()).toContain('测试内容')
  })
})
