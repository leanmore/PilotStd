// web/src/composables/useFloatingDrag.ts
// 悬浮按钮拖拽位置状态机 — Pointer Events 统一覆盖鼠标/触摸/触控笔

import { ref, onMounted, onUnmounted } from 'vue'
import { getItem, setItem } from '@/lib/storage'

const STORAGE_KEY = 'floating_workspace_pos'
const BUTTON_SIZE = 56
const EDGE_OFFSET_X = 24 // 距右 24px
const EDGE_OFFSET_Y = 32 // 距底 32px
const DRAG_THRESHOLD = 5 // 移动超过此阈值才视为拖拽
const RESIZE_DEBOUNCE = 150 // resize 防抖毫秒数

interface FloatingPosition {
  x: number
  y: number
}

export function useFloatingDrag() {
  const x = ref(0)
  const y = ref(0)

  let startX = 0
  let startY = 0
  let originX = 0
  let originY = 0
  let moved = false
  let dragging = false
  let activePointerId: number | null = null
  let suppressClick = false
  let resizeTimer: ReturnType<typeof setTimeout> | null = null

  function defaultX() { return window.innerWidth - BUTTON_SIZE - EDGE_OFFSET_X }
  function defaultY() { return window.innerHeight - BUTTON_SIZE - EDGE_OFFSET_Y }
  function clampX(v: number) { return Math.min(Math.max(v, 0), window.innerWidth - BUTTON_SIZE) }
  function clampY(v: number) { return Math.min(Math.max(v, 0), window.innerHeight - BUTTON_SIZE) }

  function loadPosition() {
    const saved = getItem(STORAGE_KEY)
    if (saved) {
      try {
        const pos = JSON.parse(saved) as FloatingPosition
        if (typeof pos.x === 'number' && typeof pos.y === 'number') {
          x.value = clampX(pos.x)
          y.value = clampY(pos.y)
          return
        }
      } catch { /* 解析失败回退默认 */ }
    }
    x.value = defaultX()
    y.value = defaultY()
  }

  function persistPosition() {
    setItem(STORAGE_KEY, JSON.stringify({ x: x.value, y: y.value }))
  }

  function onPointerDown(e: PointerEvent) {
    // 仅响应主键（鼠标左键 / 单指触摸）
    if (e.pointerType === 'mouse' && e.button !== 0) return
    startX = e.clientX
    startY = e.clientY
    originX = x.value
    originY = y.value
    moved = false
    dragging = true
    suppressClick = false
    activePointerId = e.pointerId
    ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragging || e.pointerId !== activePointerId) return
    const dx = e.clientX - startX
    const dy = e.clientY - startY
    if (!moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) moved = true
    if (moved) {
      x.value = originX + dx
      y.value = originY + dy
    }
  }

  function onPointerUp(e: PointerEvent) {
    if (!dragging || e.pointerId !== activePointerId) return
    dragging = false
    ;(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId)
    activePointerId = null
    if (moved) {
      // 拖拽释放：吞掉紧随的 click，并吸附回可视区后持久化
      suppressClick = true
      x.value = clampX(x.value)
      y.value = clampY(y.value)
      persistPosition()
    }
  }

  /** click 处理器首行调用：刚拖拽过则返回 true 并吞掉本次点击 */
  function consumeClick(): boolean {
    if (suppressClick) {
      suppressClick = false
      return true
    }
    return false
  }

  function onResize() {
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      x.value = clampX(x.value)
      y.value = clampY(y.value)
      persistPosition()
    }, RESIZE_DEBOUNCE)
  }

  onMounted(() => {
    loadPosition()
    window.addEventListener('resize', onResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    if (resizeTimer) clearTimeout(resizeTimer)
  })

  return { x, y, onPointerDown, onPointerMove, onPointerUp, consumeClick }
}
