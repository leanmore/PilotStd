// web/src/composables/useFloatingDrag.ts
// 悬浮按钮拖拽位置状态机 — Pointer Events 统一覆盖鼠标/触摸/触控笔
// 位置持久化：百分比坐标（相对视口宽高），窗口缩放/分辨率变化后相对位置不漂移；
// 旧版像素坐标数据（{x, y}）在读取时按当前视口一次性迁移为百分比。

import { ref, onMounted, onUnmounted } from 'vue'
import { getItem, setItem } from '@/lib/storage'

const STORAGE_KEY = 'floating_workspace_pos'
const BUTTON_SIZE = 56
const EDGE_OFFSET_X = 24 // 距右 24px
const EDGE_OFFSET_Y = 32 // 距底 32px
const DRAG_THRESHOLD = 5 // 移动超过此阈值才视为拖拽
const RESIZE_DEBOUNCE = 150 // resize 防抖毫秒数

/** 持久化位置：相对视口宽高的百分比坐标（0-100），窗口缩放自适应 */
interface FloatingPosition {
  xPercent: number
  yPercent: number
}

/** 旧版像素坐标格式（历史遗留），读取时一次性迁移为百分比 */
interface LegacyPosition {
  x: number
  y: number
}

/** 像素值 → 相对视口百分比（除以视口尺寸，避免直接存绝对像素） */
function toPercent(value: number, viewportSize: number): number {
  return (value / viewportSize) * 100
}

/** 百分比 → 当前视口下的像素值 */
function fromPercent(percent: number, viewportSize: number): number {
  return (percent / 100) * viewportSize
}

function isPercentPosition(pos: unknown): pos is FloatingPosition {
  const p = pos as FloatingPosition
  return Number.isFinite(p?.xPercent) && Number.isFinite(p?.yPercent)
}

function isLegacyPosition(pos: unknown): pos is LegacyPosition {
  const p = pos as LegacyPosition
  return Number.isFinite(p?.x) && Number.isFinite(p?.y)
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

  /** 持久化当前位置（百分比坐标）；可传入显式位置（旧数据迁移用） */
  function persistPosition(pos?: FloatingPosition) {
    const target: FloatingPosition = pos ?? {
      xPercent: toPercent(x.value, window.innerWidth),
      yPercent: toPercent(y.value, window.innerHeight),
    }
    setItem(STORAGE_KEY, JSON.stringify(target))
  }

  function loadPosition() {
    const saved = getItem(STORAGE_KEY)
    if (saved) {
      try {
        const pos = JSON.parse(saved)
        // 新格式：百分比坐标 → 按当前视口换算并做边界保护
        if (isPercentPosition(pos)) {
          x.value = clampX(fromPercent(pos.xPercent, window.innerWidth))
          y.value = clampY(fromPercent(pos.yPercent, window.innerHeight))
          return
        }
        // 旧格式：像素坐标 → 按当前视口一次性迁移为百分比，避免缩放后漂移
        if (isLegacyPosition(pos)) {
          persistPosition({
            xPercent: toPercent(pos.x, window.innerWidth),
            yPercent: toPercent(pos.y, window.innerHeight),
          })
          x.value = clampX(pos.x)
          y.value = clampY(pos.y)
          return
        }
      } catch { /* 脏数据/解析失败：静默回退默认位置 */ }
    }
    x.value = defaultX()
    y.value = defaultY()
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
      // 拖拽释放：吞掉紧随的 click，吸附回可视区后持久化（百分比坐标）
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
    // 百分比坐标随窗口自适应，无需重写存储；仅重新 clamp 保证图标不飞出可视区
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      x.value = clampX(x.value)
      y.value = clampY(y.value)
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
