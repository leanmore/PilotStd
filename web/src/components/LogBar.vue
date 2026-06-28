<script setup lang="ts">
defineOptions({ name: 'LogBar' })
import { ref, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'

const props = defineProps<{ refreshKey?: number }>()
const lines = ref<string[]>([])
const expanded = ref(true)
const container = ref<HTMLElement | null>(null)
const err = ref(false)
const logHeight = ref(200)
const isHovering = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
let startY = 0
let startHeight = 0

async function fetchLogs() {
  try {
    const r = await axios.get('/api/logs', { params: { tail: 80 } })
    lines.value = r.data.lines || []
    err.value = false
    // 悬停时不自动滚动，否则自动滚动到底部
    requestAnimationFrame(() => {
      if (container.value && !isHovering.value) {
        container.value.scrollTop = container.value.scrollHeight
      }
    })
  } catch {
    if (!err.value) err.value = true
    if (timer) { clearInterval(timer); timer = null }
  }
}

onMounted(() => {
  fetchLogs()
  timer = setInterval(fetchLogs, 3000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

watch(() => props.refreshKey, () => fetchLogs())

function toggle() { expanded.value = !expanded.value }

// 拖拽调整高度
function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  startY = e.clientY
  startHeight = logHeight.value
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  const delta = e.clientY - startY
  logHeight.value = Math.max(100, Math.min(600, startHeight + delta))
}

function onResizeEnd() {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
}
</script>

<template>
  <div class="log-bar" :class="{ collapsed: !expanded }">
    <div class="log-header" @click="toggle">
      <span>日志 ({{ lines.length }} 行)</span>
      <span class="log-toggle">{{ expanded ? '收起' : '展开' }}</span>
    </div>
    <div
      v-show="expanded"
      ref="container"
      class="log-body"
      :style="{ maxHeight: logHeight + 'px' }"
      @mouseenter="isHovering = true"
      @mouseleave="isHovering = false"
    >
      <div v-for="(l, i) in lines" :key="i" class="log-line" :class="{
        'log-warn': l.includes('[W]') || l.includes('WARNING'),
        'log-err': l.includes('[E]') || l.includes('ERROR'),
      }">{{ l }}</div>
      <div v-if="err" class="log-empty log-err-msg">日志加载失败（已停止轮询）</div>
      <div v-else-if="!lines.length" class="log-empty">暂无日志</div>
    </div>
    <div class="log-resize-handle" @mousedown="onResizeStart" title="拖拽调整高度" />
  </div>
</template>

<style scoped>
.log-bar {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: var(--radius-sm, 6px);
  margin-top: 12px;
  overflow: hidden;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  position: relative;
}
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #16213e;
  color: #a0aec0;
  cursor: pointer;
  user-select: none;
  font-weight: 500;
  font-size: 12px;
}
.log-toggle { font-size: 11px; opacity: 0.7; }
.log-body {
  overflow-y: auto;
  padding: 6px 12px;
  transition: max-height 0.2s ease;
}
.log-line { color: #c8d6e5; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.log-line.log-warn { color: #f0c040; }
.log-line.log-err { color: #e74c3c; }
.log-empty { color: #555; text-align: center; padding: 12px; }
.log-err-msg { color: #e74c3c; }
.collapsed .log-body { display: none; }

/* 拖拽调整高度手柄 */
.log-resize-handle {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 8px;
  cursor: ns-resize;
  background: transparent;
  z-index: 10;
  transition: background 0.2s;
}
.log-resize-handle:hover {
  background: rgba(99, 102, 241, 0.3);
}
.log-resize-handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 3px;
  background: #555;
  border-radius: 2px;
}
.log-resize-handle:hover::after {
  background: var(--primary);
  height: 4px;
}
</style>
