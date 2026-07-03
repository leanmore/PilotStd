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

// mock WidgetManager 和卡片组件，避免深层 SFC 解析链导致 vitest 误报
vi.mock('@/components/dashboard/WidgetManager.vue', () => ({
  default: { name: 'WidgetManager', template: '<div class="widget-manager-stub" />', props: ['visible'], emits: ['close'] },
}))

vi.mock('@/components/dashboard/widgets/StatsCard.vue', () => ({
  default: { name: 'StatsCard', template: '<div class="stats-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue', () => ({
  default: { name: 'AdapterStatusAnnounceCard', template: '<div class="adapter-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/AdapterStatusQueryCard.vue', () => ({
  default: { name: 'AdapterStatusQueryCard', template: '<div class="query-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/RecentAnnounceCard.vue', () => ({
  default: { name: 'RecentAnnounceCard', template: '<div class="recent-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/QuickActionsCard.vue', () => ({
  default: { name: 'QuickActionsCard', template: '<div class="quick-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/PendingItemsCard.vue', () => ({
  default: { name: 'PendingItemsCard', template: '<div class="pending-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/SystemInfoCard.vue', () => ({
  default: { name: 'SystemInfoCard', template: '<div class="system-card-stub" />', props: ['widget'] },
}))
vi.mock('@/components/dashboard/widgets/PlaceholderWidget.vue', () => ({
  default: { name: 'PlaceholderWidget', template: '<div class="placeholder-stub" />', props: ['widget'] },
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
