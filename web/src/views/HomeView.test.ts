import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import HomeView from './HomeView.vue'
import { createDefaultWidgets } from '@/types/dashboard'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'

// grid-layout-plus 在 jsdom 中无法正常渲染，mock 为简单容器组件
vi.mock('grid-layout-plus', () => ({
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
    global: { plugins: [pinia, i18n, router, PrimeVue] },
  })
}

describe('HomeView', () => {
  it('default widget library has 4 enabled widgets', () => {
    const widgets = createDefaultWidgets()
    expect(widgets.length).toBe(4)
  })

  it('default widgets include adapter-announce and adapter-query', () => {
    const widgets = createDefaultWidgets()
    const types = widgets.map(w => w.type)
    expect(types).toContain('adapter-announce')
    expect(types).toContain('adapter-query')
    expect(types).toContain('stats-summary')
    expect(types).toContain('recent-tasks')
  })

  it('mounts without error', () => {
    expect(() => mountHome()).not.toThrow()
  })
})
