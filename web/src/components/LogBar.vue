<script setup lang="ts">
defineOptions({ name: 'LogBar' })
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import http from '@/api/http'
import { getItem, setItem } from '@/lib/storage'

const props = defineProps<{ refreshKey?: number }>()
const lines = ref<string[]>([])
const expanded = ref(getItem('logbar_expanded') !== '0')
const container = ref<HTMLElement | null>(null)
const err = ref(false)
const route = useRoute()

// 增量游标：上次请求获取到的最后一条日志的时间戳
const lastTimestamp = ref<string>('')

// 每个页面默认日志面板高度
const defaultHeights: Record<string, number> = {
  '/task': 300,
  '/pending': 150,
  '/organize': 200,
  '/announce': 200,
}

const heightKey = computed(() => {
  const path = route?.path
  return path ? `logbar_height_${path.replace(/\//g, '_')}` : 'logbar_height_global_default'
})

const defaultHeight = computed(() => {
  if (!route?.path) return 200
  return defaultHeights[route.path] || 200
})

const logHeight = ref(
  Number(getItem(heightKey.value)) || defaultHeight.value
)

// 用户手动滚离顶部时置 true，暂停自动滚动
const userScrolled = ref(false)
// ✅ #45: 滚动阈值常量（原硬编码 50）
const SCROLL_THRESHOLD = 50
let timer: ReturnType<typeof setInterval> | null = null
let startY = 0
let startHeight = 0

// 行内容稳定 hash（前 32 字符，避免长行性能开销）
function lineHash(l: string): string {
  return l.substring(0, 32)
}

function onScroll() {
  if (!container.value) return
  // 用户向上滚动超过阈值 → 锁定；滚回顶部 → 解锁
  userScrolled.value = container.value.scrollTop > SCROLL_THRESHOLD
}

async function fetchLogs() {
  try {
    // 增量请求：传入上次游标，后端只返回新行
    const params: Record<string, string | number> = { tail: 80 }
    const isFirstLoad = !lastTimestamp.value
    if (lastTimestamp.value) {
      params.since = lastTimestamp.value
    }
    const r = await http.get('/logs', { params })
    const newLines: string[] = r.data.lines || []
    err.value = false

    if (r.data.lastTimestamp) {
      lastTimestamp.value = r.data.lastTimestamp
    }

    if (newLines.length > 0) {
      if (isFirstLoad) {
        // 首次全量：后端返回正序（旧→新），反转使最新日志置顶
        lines.value = [...newLines].reverse().slice(0, 200)
      } else {
        // 增量：新日志前置追加，保持倒序，最新在顶
        lines.value = [...newLines, ...lines.value].slice(0, 200)
      }
    }

    // 仅当用户未锁定且日志面板展开时，滚到顶部（最新日志在上）
    if (!userScrolled.value && expanded.value) {
      await nextTick()
      if (container.value) {
        container.value.scrollTop = 0
      }
    }
  } catch {
    if (!err.value) err.value = true
    // 网络错误时不清除定时器，等待下次重试
  }
}

onMounted(() => {
  fetchLogs()
  timer = setInterval(fetchLogs, 3000)
})
// ✅ #45: onBeforeUnmount 防御性清理拖拽监听器 + 定时器
onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})

watch(() => props.refreshKey, () => {
  // 手动刷新：清空游标重新加载
  lastTimestamp.value = ''
  fetchLogs()
})

function toggle() { expanded.value = !expanded.value; setItem('logbar_expanded', expanded.value ? '1' : '0') }

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
  setItem(heightKey.value, String(logHeight.value))
}

// 路由切换时重新加载该页面对应的高度
watch(() => route?.path, () => {
  if (!route?.path) return
  const saved = Number(getItem(heightKey.value))
  logHeight.value = (saved && saved > 0) ? saved : defaultHeight.value
})
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
      @scroll="onScroll"
    >
      <div v-for="l in lines" :key="lineHash(l)" class="log-line" :class="{
        'log-warn': l.includes('[W]') || l.includes('WARNING'),
        'log-err': l.includes('[E]') || l.includes('ERROR'),
      }" :title="l">{{ l }}</div>
      <div v-if="err" class="log-empty log-err-msg">日志加载失败（已停止轮询）</div>
      <div v-else-if="!lines.length" class="log-empty">暂无日志</div>
    </div>
    <div class="log-resize-handle" @mousedown="onResizeStart" title="拖拽调整高度" />
  </div>
</template>

<style scoped>
/* fix(theme): 日志栏跟随主题——替代硬编码 terminal 色（原 #1a1a2e/#16213e/#c8d6e5）；
   背景 --p-surface-0、正文 --p-content-color（Aura token 随主题注入），级别标签 [I] 用 --text-dim、[W]/[E] 用语义色 */
.log-bar {
  background: var(--p-surface-0);
  border: var(--mp-card-border, 1px solid var(--p-surface-200));
  border-radius: var(--radius-sm, 6px);
  margin-top: 12px;
  overflow: hidden;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  position: relative;
  color: var(--p-content-color);
}
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: var(--surface-raised);
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  font-weight: 500;
  font-size: 12px;
}
.log-toggle { font-size: 11px; opacity: 0.7; }
.log-body {
  overflow: auto;
  padding: 6px 12px;
  transition: max-height 0.2s ease;
}
/* [I]/普通日志行：弱化辅助文字（重设计后 --text-dim 四主题 ≥4.5:1） */
.log-line { color: var(--text-dim); line-height: 1.5; white-space: pre; }
/* [W] 警告行：语义色（非 dim，保持醒目） */
.log-line.log-warn { color: var(--warning); }
/* [E] 错误行：语义色（非 dim） */
.log-line.log-err { color: var(--danger); }
.log-empty { color: var(--text-dim); text-align: center; padding: 12px; }
.log-err-msg { color: var(--danger); }
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
