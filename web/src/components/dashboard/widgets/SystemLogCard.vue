<script setup lang="ts">
defineOptions({ name: 'SystemLogCard' })
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'

interface LogEntry { time: string; level: string; message: string }

const logs = ref<LogEntry[]>([])
const logContainer = ref<HTMLElement | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

function scrollToBottom() {
  nextTick(() => { if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight })
}

function parseLine(line: string): LogEntry {
  // 解析 "MM-DD HH:MM:SS [LEVEL] TAG message" 格式
  const m = line.match(/^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+\S+\s+(.*)/)
  if (m) return { time: m[1] || '', level: (m[2] || 'info').toLowerCase(), message: m[3] || line }
  return { time: '', level: 'info', message: line }
}

const levelIcon: Record<string, string> = { info: 'pi pi-info-circle', warn: 'pi pi-exclamation-triangle', error: 'pi pi-times-circle', debug: 'pi pi-code' }

async function fetchLogs() {
  try {
    const r = await http.get('/logs', { params: { tail: 30 } })
    const lines: string[] = r.data?.logs || r.data?.lines || r.data || []
    logs.value = (Array.isArray(lines) ? lines : []).map(parseLine)
    scrollToBottom()
  } catch { /* ignore */ }
}

onMounted(() => { fetchLogs(); timer = setInterval(fetchLogs, 8000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-terminal" /></div>
        <div>
          <div class="header-title">系统日志</div>
          <div class="header-sub">{{ logs.length }} 行 · 8s 刷新</div>
        </div>
      </div>
      <button class="clear-btn" @click="logs = []">清空</button>
    </div>

    <div ref="logContainer" class="log-box">
      <div v-if="!logs.length" class="empty">等待日志...</div>
      <div v-for="(l, idx) in logs" :key="idx" class="line">
        <i v-if="levelIcon[l.level]" :class="['li', levelIcon[l.level], 'lv-' + l.level]" />
        <span class="lt">{{ l.time }}</span>
        <span class="lm">{{ l.message }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: 14px;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: 10px;
}
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon {
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(34,197,94,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--success); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
.header-sub { font-size: 10px; color: var(--text-dim); }
.clear-btn {
  font-size: 10px; color: var(--text-dim); background: none; border: 1px solid var(--border-light);
  border-radius: var(--radius-sm); padding: 2px 8px; cursor: pointer;
}
.clear-btn:hover { color: var(--danger); border-color: var(--danger); }

.log-box {
  flex: 1; overflow-y: auto; background: rgba(0,0,0,0.05); border-radius: var(--radius);
  padding: 8px 10px; font-family: var(--mono); font-size: 11px; line-height: 1.7;
}
.empty { color: var(--text-dim); text-align: center; padding: 20px 0; }
.line { display: flex; gap: 8px; align-items: baseline; }
.li { font-size: 10px; flex-shrink: 0; margin-top: 3px; }
.lt { color: var(--text-dim); flex-shrink: 0; font-size: 10px; }
.lm { color: var(--text-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lv-info { color: var(--info); }
.lv-warn,.lv-warning { color: var(--warning); }
.lv-error { color: var(--danger); }
.lv-debug { color: var(--text-dim); }
</style>
