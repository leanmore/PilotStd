<script setup lang="ts">
defineOptions({ name: 'SystemLogCard' })
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'

interface LogEntry { time: string; level: string; message: string }

const logs = ref<LogEntry[]>([])
const logContainer = ref<HTMLElement | null>(null)
const clearing = ref(false)
const clearMsg = ref('')
const clearErr = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

function scrollToBottom() {
  nextTick(() => { if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight })
}

function parseLine(line: string): LogEntry {
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

async function clearOldLogs(hours: number) {
  clearing.value = true
  try {
    const r = await http.delete('/admin/logs', { params: { before_hours: hours } })
    const deleted = r.data?.deleted ?? 0
    clearMsg.value = hours > 0 ? `已清理 ${deleted} 条日志（${hours}h 前）` : `已清空全部日志（${deleted} 条）`
    clearErr.value = false
    await fetchLogs()
  } catch {
    clearMsg.value = '清理日志失败'
    clearErr.value = true
  } finally {
    clearing.value = false
    setTimeout(() => { clearMsg.value = '' }, 3000)
  }
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
      <div class="header-actions">
        <button class="clear-btn" :disabled="clearing" @click="clearOldLogs(24)">清理旧日志</button>
        <button class="clear-btn clear-all" :disabled="clearing" @click="clearOldLogs(0)">清空</button>
      </div>
    </div>
    <div v-if="clearMsg" class="clear-msg" :class="{ error: clearErr }">{{ clearMsg }}</div>

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
.header-actions { display: flex; gap: 6px; }
.clear-btn {
  font-size: 10px; color: var(--text-dim); background: none; border: 1px solid var(--border-light);
  border-radius: var(--radius-sm); padding: 2px 8px; cursor: pointer; white-space: nowrap;
}
.clear-btn:hover:not(:disabled) { color: var(--warning); border-color: var(--warning); }
.clear-all:hover:not(:disabled) { color: var(--danger); border-color: var(--danger); }
.clear-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.log-box {
  flex: 1; overflow-y: auto; background: rgba(0,0,0,0.08); border-radius: var(--radius);
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
.clear-msg { font-size: 11px; color: var(--success); }
.clear-msg.error { color: var(--danger); }
</style>
