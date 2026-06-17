import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import HomeView from './HomeView.vue'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'

function mountHome() {
  setActivePinia(createPinia())
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: HomeView }],
  })
  return mount(HomeView, {
    global: { plugins: [createPinia(), i18n, router, PrimeVue] },
  })
}

describe('HomeView', () => {
  it('renders 4 stat cards', () => {
    const wrapper = mountHome()
    const cards = wrapper.findAll('.stat-card')
    expect(cards.length).toBe(4)
  })

  it('stat cards show skeleton loading when API not loaded', () => {
    const wrapper = mountHome()
    // API 未加载时显示骨架动画，不是占位符文字
    const skeletons = wrapper.findAll('.skeleton')
    expect(skeletons.length).toBe(4)
  })

  it('renders 3 action buttons', () => {
    const wrapper = mountHome()
    const buttons = wrapper.findAll('button')
    // At least 3: 手动扫描, 手动查询, 一键更新
    expect(buttons.length).toBeGreaterThanOrEqual(3)
  })
})
