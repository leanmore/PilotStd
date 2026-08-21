// web/src/composables/useFloatingDrag.test.ts
// 覆盖：默认坐标、百分比坐标加载/持久化、旧像素格式迁移、脏数据容错、
// 阈值内不拖拽（不写存储）、超阈值拖拽、释放 clamp、resize 自适应

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { useFloatingDrag } from './useFloatingDrag'
import { getItem, setItem } from '@/lib/storage'

const BTN_SIZE = 56
const EDGE_X = 24
const EDGE_Y = 32
const VIEW_W = 1024
const VIEW_H = 768

const TestComponent = defineComponent({
  setup() {
    return useFloatingDrag()
  },
  template: '<div />',
})

function makePointer(partial: Partial<PointerEvent> = {}): PointerEvent {
  return {
    pointerId: 1,
    pointerType: 'mouse',
    button: 0,
    clientX: 0,
    clientY: 0,
    currentTarget: { setPointerCapture: vi.fn(), releasePointerCapture: vi.fn() },
    ...partial,
  } as unknown as PointerEvent
}

type DragVm = {
  x: number
  y: number
  onPointerDown: (e: PointerEvent) => void
  onPointerMove: (e: PointerEvent) => void
  onPointerUp: (e: PointerEvent) => void
  consumeClick: () => boolean
}

describe('useFloatingDrag', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: VIEW_W })
    Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: VIEW_H })
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('无存储时使用默认右下角坐标', () => {
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    expect(vm.x).toBe(VIEW_W - BTN_SIZE - EDGE_X)
    expect(vm.y).toBe(VIEW_H - BTN_SIZE - EDGE_Y)
  })

  it('有存储时按百分比坐标加载', () => {
    // 100px / 1024 ≈ 9.766%，200px / 768 ≈ 26.042%
    setItem('floating_workspace_pos', JSON.stringify({
      xPercent: (100 / VIEW_W) * 100,
      yPercent: (200 / VIEW_H) * 100,
    }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    expect(vm.x).toBeCloseTo(100, 5)
    expect(vm.y).toBeCloseTo(200, 5)
  })

  it('旧像素格式读取时一次性迁移为百分比', () => {
    setItem('floating_workspace_pos', JSON.stringify({ x: 100, y: 200 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    expect(vm.x).toBe(100)
    expect(vm.y).toBe(200)
    // 存储应已被重写为百分比格式
    const stored = JSON.parse(getItem('floating_workspace_pos')!) as Record<string, number>
    expect(stored.xPercent).toBeCloseTo((100 / VIEW_W) * 100, 5)
    expect(stored.yPercent).toBeCloseTo((200 / VIEW_H) * 100, 5)
    expect('x' in stored).toBe(false)
    expect('y' in stored).toBe(false)
  })

  it('脏数据回退默认位置且不抛错', () => {
    setItem('floating_workspace_pos', 'not-json{{{')
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    expect(vm.x).toBe(VIEW_W - BTN_SIZE - EDGE_X)
    expect(vm.y).toBe(VIEW_H - BTN_SIZE - EDGE_Y)
  })

  it('超界百分比被 clamp 到可视区内', () => {
    setItem('floating_workspace_pos', JSON.stringify({ xPercent: 200, yPercent: -50 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    expect(vm.x).toBe(VIEW_W - BTN_SIZE)
    expect(vm.y).toBe(0)
  })

  it('移动小于阈值不触发拖拽，click 不被吞掉且不写存储', () => {
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as DragVm
    const startX = vm.x
    const startY = vm.y
    vm.onPointerDown(makePointer({ clientX: 500, clientY: 500 }))
    vm.onPointerMove(makePointer({ clientX: 502, clientY: 502 })) // 位移 < 5px
    vm.onPointerUp(makePointer({ clientX: 502, clientY: 502 }))
    expect(vm.x).toBe(startX)
    expect(vm.y).toBe(startY)
    expect(vm.consumeClick()).toBe(false)
    // 点击不应产生位置写入
    expect(localStorage.getItem('pilotstd_floating_workspace_pos')).toBeNull()
  })

  it('移动超过阈值触发拖拽并以百分比持久化', () => {
    setItem('floating_workspace_pos', JSON.stringify({
      xPercent: (400 / VIEW_W) * 100,
      yPercent: (400 / VIEW_H) * 100,
    }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as DragVm
    vm.onPointerDown(makePointer({ clientX: 400, clientY: 400 }))
    vm.onPointerMove(makePointer({ clientX: 500, clientY: 450 })) // dx=100, dy=50，均在可视区内
    expect(vm.x).toBe(500)
    expect(vm.y).toBe(450)
    vm.onPointerUp(makePointer({ clientX: 500, clientY: 450 }))
    expect(vm.consumeClick()).toBe(true)
    const stored = JSON.parse(getItem('floating_workspace_pos')!) as Record<string, number>
    expect(stored.xPercent).toBeCloseTo((500 / VIEW_W) * 100, 5)
    expect(stored.yPercent).toBeCloseTo((450 / VIEW_H) * 100, 5)
  })

  it('拖拽释放后 clamp 吸附到可视区', () => {
    setItem('floating_workspace_pos', JSON.stringify({
      xPercent: (400 / VIEW_W) * 100,
      yPercent: (400 / VIEW_H) * 100,
    }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as DragVm
    vm.onPointerDown(makePointer({ clientX: 400, clientY: 400 }))
    vm.onPointerMove(makePointer({ clientX: -200, clientY: -200 })) // dx=-600，拖出左上边界
    vm.onPointerUp(makePointer({ clientX: -200, clientY: -200 }))
    expect(vm.x).toBe(0)
    expect(vm.y).toBe(0)
  })

  it('窗口 resize 后仅 clamp 显示值，百分比存储不变', () => {
    setItem('floating_workspace_pos', JSON.stringify({ xPercent: 100, yPercent: 100 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    // 100% 在 1024x768 下贴右下角
    expect(vm.x).toBe(VIEW_W - BTN_SIZE)
    expect(vm.y).toBe(VIEW_H - BTN_SIZE)
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 500 })
    Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 400 })
    window.dispatchEvent(new Event('resize'))
    vi.advanceTimersByTime(200) // 超过 150ms 防抖
    // 显示位置被 clamp 到新视口安全区
    expect(vm.x).toBe(500 - BTN_SIZE)
    expect(vm.y).toBe(400 - BTN_SIZE)
    // 存储仍是百分比（不随窗口缩放被像素覆盖）
    const stored = JSON.parse(getItem('floating_workspace_pos')!) as Record<string, number>
    expect(stored.xPercent).toBe(100)
    expect(stored.yPercent).toBe(100)
  })
})
