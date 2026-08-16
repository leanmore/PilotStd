// web/src/composables/useFloatingDrag.test.ts
// 覆盖默认坐标、阈值内不拖拽、超阈值拖拽、释放 clamp、storage 读写、resize 校验

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

  it('有存储时加载存储坐标', () => {
    setItem('floating_workspace_pos', JSON.stringify({ x: 100, y: 200 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    expect(vm.x).toBe(100)
    expect(vm.y).toBe(200)
  })

  it('移动小于阈值不触发拖拽，click 不被吞掉', () => {
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as {
      x: number; y: number
      onPointerDown: (e: PointerEvent) => void
      onPointerMove: (e: PointerEvent) => void
      onPointerUp: (e: PointerEvent) => void
      consumeClick: () => boolean
    }
    const startX = vm.x
    const startY = vm.y
    vm.onPointerDown(makePointer({ clientX: 500, clientY: 500 }))
    vm.onPointerMove(makePointer({ clientX: 502, clientY: 502 })) // 位移 < 5px
    vm.onPointerUp(makePointer({ clientX: 502, clientY: 502 }))
    expect(vm.x).toBe(startX)
    expect(vm.y).toBe(startY)
    expect(vm.consumeClick()).toBe(false)
  })

  it('移动超过阈值触发拖拽并持久化坐标', () => {
    setItem('floating_workspace_pos', JSON.stringify({ x: 400, y: 400 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as {
      x: number; y: number
      onPointerDown: (e: PointerEvent) => void
      onPointerMove: (e: PointerEvent) => void
      onPointerUp: (e: PointerEvent) => void
      consumeClick: () => boolean
    }
    vm.onPointerDown(makePointer({ clientX: 400, clientY: 400 }))
    vm.onPointerMove(makePointer({ clientX: 500, clientY: 450 })) // dx=100, dy=50，均在可视区内
    expect(vm.x).toBe(500)
    expect(vm.y).toBe(450)
    vm.onPointerUp(makePointer({ clientX: 500, clientY: 450 }))
    expect(vm.consumeClick()).toBe(true)
    expect(JSON.parse(getItem('floating_workspace_pos')!)).toEqual({ x: 500, y: 450 })
  })

  it('拖拽释放后 clamp 吸附到可视区', () => {
    setItem('floating_workspace_pos', JSON.stringify({ x: 400, y: 400 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as {
      x: number; y: number
      onPointerDown: (e: PointerEvent) => void
      onPointerMove: (e: PointerEvent) => void
      onPointerUp: (e: PointerEvent) => void
    }
    vm.onPointerDown(makePointer({ clientX: 400, clientY: 400 }))
    vm.onPointerMove(makePointer({ clientX: -200, clientY: -200 })) // dx=-600，拖出左上边界
    vm.onPointerUp(makePointer({ clientX: -200, clientY: -200 }))
    expect(vm.x).toBe(0)
    expect(vm.y).toBe(0)
  })

  it('窗口 resize 后重新校验坐标并写回', () => {
    setItem('floating_workspace_pos', JSON.stringify({ x: 900, y: 700 }))
    const wrapper = mount(TestComponent)
    const vm = wrapper.vm as unknown as { x: number; y: number }
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 500 })
    Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: 400 })
    window.dispatchEvent(new Event('resize'))
    vi.advanceTimersByTime(200) // 超过 150ms 防抖
    expect(vm.x).toBe(500 - BTN_SIZE)
    expect(vm.y).toBe(400 - BTN_SIZE)
    expect(JSON.parse(getItem('floating_workspace_pos')!)).toEqual({ x: 500 - BTN_SIZE, y: 400 - BTN_SIZE })
  })
})
