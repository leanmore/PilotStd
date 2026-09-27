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

// 2026-09-27：路由 fixture 补齐 meta.showInSidebar/titleKey/sidebarOrder——原 fixture 无任何
// showInSidebar 标记，侧边栏项实际来自组件内已删除的"空列表兜底"；现按真实 router.ts 的 meta 形态构造。
const Dummy = { template: '<div />' }
const routes = [
  { path: '/', component: { template: '<div>Home</div>' }, meta: { showInSidebar: true, titleKey: 'nav.home', sidebarOrder: 1 } },
  { path: '/task', component: Dummy, meta: { showInSidebar: true, titleKey: 'nav.task', sidebarOrder: 2 } },
  { path: '/organize', component: Dummy, meta: { showInSidebar: true, titleKey: 'nav.organize', sidebarOrder: 3 } },
  { path: '/pending', component: Dummy, meta: { showInSidebar: true, titleKey: 'nav.pending', sidebarOrder: 4 } },
  { path: '/announce', component: Dummy, meta: { showInSidebar: true, titleKey: 'nav.announce', sidebarOrder: 6 } },
  { path: '/notification-logs', component: Dummy, meta: { showInSidebar: true, titleKey: 'nav.notification_logs', sidebarOrder: 7 } },
  { path: '/standards-status', component: Dummy, meta: { showInSidebar: true, titleKey: 'nav.standards_status', sidebarOrder: 8 } },
  { path: '/settings', component: Dummy, meta: { showInSidebar: true, permission: 'user', titleKey: 'nav.settings', sidebarOrder: 9 } },
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