<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'

const props = defineProps<{ refreshKey?: number }>()
const lines = ref<string[]>([])
const expanded = ref(true)
const container = ref<HTMLElement | null>(null)
const err = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

async function fetchLogs() {
  try {
    const r = await axios.get('/api/logs', { params: { tail: 80 } })
    lines.value = r.data.lines || []
    err.value = false
    requestAnimationFrame(() => {
      if (container.value) container.value.scrollTop = container.value.scrollHeight
    })
  } catch {
    if (!err.value) err.value = true  // 首次失败标记，不反复刷
    if (timer) { clearInterval(timer); timer = null }  // 停止轮询
  }
}

onMounted(() => {
  fetchLogs()
  timer = setInterval(fetchLogs, 3000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

// 外部可通过 refreshKey 强制刷新
watch(() => props.refreshKey, () => fetchLogs())

function toggle() { expanded.value = !expanded.value }
</script>

<template>
  <div class="log-bar" :class="{ collapsed: !expanded }">
    <div class="log-header" @click="toggle">
      <span>日志 ({{ lines.length }} 行)</span>
      <span class="log-toggle">{{ expanded ? '收起' : '展开' }}</span>
    </div>
    <div v-show="expanded" ref="container" class="log-body">
      <div v-for="(l, i) in lines" :key="i" class="log-line" :class="{
        'log-warn': l.includes('[W]') || l.includes('WARNING'),
        'log-err': l.includes('[E]') || l.includes('ERROR'),
      }">{{ l }}</div>
      <div v-if="err" class="log-empty log-err-msg">日志加载失败（已停止轮询）</div>
      <div v-else-if="!lines.length" class="log-empty">暂无日志</div>
    </div>
  </div>
</template>

<style scoped>
.log-bar { background: #1a1a2e; border: 1px solid #333; border-radius: var(--radius-sm, 6px); margin-top: 12px; overflow: hidden; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 11px; }
.log-header { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; background: #16213e; color: #a0aec0; cursor: pointer; user-select: none; font-weight: 500; font-size: 12px; }
.log-toggle { font-size: 11px; opacity: 0.7; }
.log-body { max-height: 200px; overflow-y: auto; padding: 6px 12px; }
.log-line { color: #c8d6e5; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.log-line.log-warn { color: #f0c040; }
.log-line.log-err { color: #e74c3c; }
.log-empty { color: #555; text-align: center; padding: 12px; }
.log-err-msg { color: #e74c3c; }
.collapsed .log-body { display: none; }
</style>
