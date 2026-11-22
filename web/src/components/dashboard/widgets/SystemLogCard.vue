<script setup lang="ts">
defineOptions({ name: 'SystemLogCard' })
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()

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
    const r = await http.get('/logs', { params: { tail: 30 }, routeTag: '/' })
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
    clearMsg.value = hours > 0 ? t('dashboard.sys_log.cleared', { n: deleted, h: hours }) : t('dashboard.sys_log.cleared_all', { n: deleted })
    clearErr.value = false
    await fetchLogs()
  } catch {
    clearMsg.value = t('dashboard.sys_log.clear_failed')
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
          <div class="header-title">{{ t('dashboard.card.sysLog') }}</div>
          <div class="header-sub">{{ t('dashboard.sys_log.subtitle', { n: logs.length }) }}</div>
        </div>
      </div>
      <div class="header-actions">
        <AppButton class="clear-btn" :disabled="clearing" @click="clearOldLogs(24)"
  size="s"
  type="danger"
>{{ t('dashboard.sys_log.clear_old') }}</AppButton>
        <AppButton class="clear-btn clear-all" :disabled="clearing" @click="clearOldLogs(0)"
  size="s"
  type="danger"
>{{ t('dashboard.sys_log.clear_all') }}</AppButton>
      </div>
    </div>
    <div v-if="clearMsg" class="clear-msg" :class="{ error: clearErr }">{{ clearMsg }}</div>

    <div ref="logContainer" class="log-box">
      <div v-if="!logs.length" class="empty">{{ t('dashboard.sys_log.waiting') }}</div>
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
  height: 100%; box-sizing: border-box; padding: var(--space-14);
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: var(--space-10);
}
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: var(--space-10); }
.header-icon {
  width: 34px; height: var(--icon-tile-md); border-radius: var(--radius-sm); background: var(--success-bg);
  display: flex; align-items: center; justify-content: center; color: var(--success); font-size: var(--font-size-16);
}
.header-title { font-size: var(--font-size-13); font-weight: var(--font-weight-bold); color: var(--text-heading); }
.header-sub { font-size: var(--font-size-10); color: var(--text-dim); }
.header-actions { display: flex; gap: var(--space-6); }
.clear-btn {
  font-size: var(--font-size-10); color: var(--text-dim); background: none; border: 1px solid var(--border-light);
  border-radius: var(--radius-sm); padding: var(--space-2) var(--space-8); cursor: pointer; white-space: nowrap;
}
.clear-btn:hover:not(:disabled) { color: var(--warning); border-color: var(--warning); }
.clear-all:hover:not(:disabled) { color: var(--danger); border-color: var(--danger); }
.clear-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.log-box {
  /* TODO: [Design Debt] rgba(0,0,0,0.08) 无精确令牌，暂不替换，待定令牌后统一处理 */
  flex: 1; overflow-y: auto; background: rgba(0,0,0,0.08); border-radius: var(--radius);
  padding: var(--space-8) var(--space-10); font-family: var(--mono); font-size: var(--font-size-11); line-height: var(--line-height-relaxed);
}
.empty { color: var(--text-dim); text-align: center; padding: var(--space-20) 0; }
.line { display: flex; gap: var(--space-8); align-items: baseline; }
.li { font-size: var(--font-size-10); flex-shrink: 0; margin-top: var(--space-3); }
.lt { color: var(--text-dim); flex-shrink: 0; font-size: var(--font-size-10); }
.lm { color: var(--text-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lv-info { color: var(--info); }
.lv-warn,.lv-warning { color: var(--warning); }
.lv-error { color: var(--danger); }
.lv-debug { color: var(--text-dim); }
.clear-msg { font-size: var(--font-size-11); color: var(--success); }
.clear-msg.error { color: var(--danger); }
</style>
