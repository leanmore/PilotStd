// HomeView 测试（仪表盘装配层）
//
// 布局状态由 useDashboard 模块级单例承载（其内部逻辑另有 __tests__/HomeView.test.ts 覆盖），
// 本文件锁定视图装配契约：挂载即 fetchLayout；GridLayout 的可拖拽/可缩放与移除按钮
// 都跟随 dashboardLocked；解锁时克隆 layout 规避 grid-layout-plus 拖拽监听器不重绑的缺陷；
// 重新锁定触发布局落库。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import HomeView from './HomeView.vue'

// 组件 watch 了全局 store：必须逐例卸载，否则上一例的 watcher 会把本例的 mock 打脏
enableAutoUnmount(afterEach)

const h = vi.hoisted(() => ({
  layout: null as unknown as { value: Array<Record<string, unknown>> },
  store: null as unknown as { dashboardLocked: boolean },
  fetchLayout: vi.fn(),
  handleLayoutUpdated: vi.fn(),
  removeCard: vi.fn(),
  saveLayoutToServer: vi.fn(),
}))

vi.mock('@/composables/useDashboard', async () => {
  const { ref } = await import('vue')
  h.layout = ref([]) as never
  return {
    useDashboard: () => ({
      layout: h.layout,
      fetchLayout: h.fetchLayout,
      handleLayoutUpdated: h.handleLayoutUpdated,
      removeCard: h.removeCard,
      saveLayoutToServer: h.saveLayoutToServer,
    }),
  }
})
vi.mock('@/stores/app', async () => {
  const { reactive } = await import('vue')
  h.store = reactive({ dashboardLocked: true }) as never
  return { useAppStore: () => h.store }
})
vi.mock('grid-layout-plus', () => ({
  GridLayout: {
    name: 'GridLayout',
    props: ['layout', 'colNum', 'rowHeight', 'isDraggable', 'isResizable', 'verticalCompact', 'useCssTransforms', 'margin'],
    emits: ['update:layout'],
    template: '<div class="mock-grid"><slot /></div>',
  },
  GridItem: {
    name: 'GridItem',
    props: ['i', 'x', 'y', 'w', 'h', 'minW', 'minH'],
    template: '<div class="mock-item"><slot /></div>',
  },
}))

const CardA = { name: 'CardA', props: ['titleKey'], template: '<div class="card-a">{{ titleKey }}</div>' }

function twoCards() {
  return [
    { i: 'stats', x: 0, y: 0, w: 4, h: 6, component: CardA, titleKey: 'dashboard.card.stats' },
    { i: 'sysInfo', x: 4, y: 0, w: 4, h: 6, component: CardA, titleKey: 'dashboard.card.sysInfo' },
  ]
}

describe('HomeView 仪表盘布局', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.store.dashboardLocked = true
    h.layout.value = twoCards()
  })

  it('挂载即调用 fetchLayout 拉取用户布局', async () => {
    mount(HomeView)
    await flushPromises()
    expect(h.fetchLayout).toHaveBeenCalledTimes(1)
  })

  it('按 layout 渲染 GridItem 数量，并把 titleKey 交给卡片组件', () => {
    const wrapper = mount(HomeView)
    expect(wrapper.findAll('.mock-item').length).toBe(2)
    expect(wrapper.text()).toContain('dashboard.card.stats')
  })

  it('锁定态：GridLayout 不可拖拽不可缩放，且不渲染移除按钮', () => {
    const wrapper = mount(HomeView)
    const grid = wrapper.findComponent({ name: 'GridLayout' })
    expect(grid.props('isDraggable')).toBe(false)
    expect(grid.props('isResizable')).toBe(false)
    expect(wrapper.findAll('.remove-btn').length).toBe(0)
  })

  it('解锁后 GridLayout 可拖拽/缩放，每张卡片出现移除按钮', async () => {
    const wrapper = mount(HomeView)
    h.store.dashboardLocked = false
    await nextTick()

    const grid = wrapper.findComponent({ name: 'GridLayout' })
    expect(grid.props('isDraggable')).toBe(true)
    expect(grid.props('isResizable')).toBe(true)
    expect(wrapper.findAll('.remove-btn').length).toBe(2)
  })

  it('点击移除按钮按卡片 key 调用 removeCard', async () => {
    const wrapper = mount(HomeView)
    h.store.dashboardLocked = false
    await nextTick()

    await wrapper.findAll('.remove-btn')[0].trigger('click')
    expect(h.removeCard).toHaveBeenCalledWith('stats')
  })

  it('解锁时克隆 layout（触发 GridItem 重挂载）；重新锁定时保存布局到服务端', async () => {
    mount(HomeView)
    const before = h.layout.value

    h.store.dashboardLocked = false
    await nextTick()
    expect(h.layout.value).not.toBe(before)
    expect(h.layout.value.map((c) => c.i)).toEqual(['stats', 'sysInfo'])
    expect(h.saveLayoutToServer).not.toHaveBeenCalled()

    h.store.dashboardLocked = true
    await nextTick()
    expect(h.saveLayoutToServer).toHaveBeenCalledTimes(1)
  })
})
