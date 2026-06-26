import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import HomeView from './HomeView.vue'
import { useDashboardStore } from '@/stores/dashboard'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'

// vue-grid-layout 在 jsdom 中无法正常 import，mock 为简单容器组件
vi.mock('vue-grid-layout', () => ({
  GridLayout: {
    name: 'GridLayout',
    template: '<div class="grid-layout"><slot /></div>',
    props: ['layout', 'colNum', 'rowHeight', 'isDraggable', 'isResizable', 'margin', 'useCssTransforms', 'verticalCompact'],
    emits: ['update:layout'],
  },
  GridItem: {
    name: 'GridItem',
    template: '<div class="grid-item"><slot /></div>',
    props: ['i', 'x', 'y', 'w', 'h', 'minW', 'minH'],
  },
}))

function mountHome() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: HomeView }],
  })
  return mount(HomeView, {
    global: {
      plugins: [pinia, i18n, router, PrimeVue],
    },
  })
}

describe('HomeView', () => {
  it('renders 4 stat cards from default layout', () => {
    mountHome()
    const store = useDashboardStore()
    const statCards = store.widgets.filter(w => w.type === 'stats-card')
    expect(statCards.length).toBe(4)
  })

  it('stat cards show skeleton loading when API not loaded', () => {
    const wrapper = mountHome()
    // StatsCard 加载中渲染 .skeleton-box（图标占位）和 .skeleton-num / .skeleton-label（文字占位）
    // 每个 card：1 个 box + 1 个 num + 1 个 label = 共 4 组
    const skeletonBoxes = wrapper.findAll('.skeleton-box')
    const skeletonNums = wrapper.findAll('.skeleton-num')
    const skeletonLabels = wrapper.findAll('.skeleton-label')
    expect(skeletonBoxes.length).toBe(4)
    expect(skeletonNums.length).toBe(4)
    expect(skeletonLabels.length).toBe(4)
  })

  it('renders 4 action buttons in QuickActionsCard', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDashboardStore()
    // 默认布局不含 quick-actions，手动添加到 store
    store.widgets.push({
      id: 'quick-actions',
      type: 'quick-actions',
      layout: { i: 'quick-actions', x: 0, y: 6, w: 12, h: 4, minW: 3, minH: 3 },
      config: { title: '快捷操作' },
    })

    const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: HomeView }],
    })
    const wrapper = mount(HomeView, {
      global: {
        plugins: [pinia, i18n, router, PrimeVue],
      },
    })

    const buttons = wrapper.findAll('.action-btn')
    expect(buttons.length).toBe(4)
  })
})
