<script setup lang="ts">
// AdapterStatusCard.vue — 适配器熔断状态 Widget（从 DashboardView 迁移）
import { ref, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import Tag from 'primevue/tag'
import Button from 'primevue/button'

interface AdapterStatus {
  name: string
  status: string
  frozen_until: string | null
  remaining_seconds: number
  freeze_count: number
  fail_streak: number
}

const adapters = ref<AdapterStatus[]>([])
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setInterval> | null = null

async function loadStatus() {
  loading.value = true
  try {
    const r = await http.get('/adapter/status')
    adapters.value = r.data.adapters
    error.value = ''
  } catch {
    error.value = '加载适配器状态失败'
  } finally {
    loading.value = false
  }
}

function tick() {
  let anyFrozen = false
  for (const a of adapters.value) {
    if (a.status === 'frozen' && a.remaining_seconds > 0) {
      a.remaining_seconds--
      anyFrozen = true
    }
  }
  if (!anyFrozen && adapters.value.some(a => a.status === 'frozen')) {
    loadStatus()
  }
}

function statusSeverity(s: string): 'success' | 'danger' | 'info' {
  if (s === 'frozen') return 'danger'
  if (s === 'normal') return 'success'
  return 'info'
}

function statusLabel(s: string): string {
  if (s === 'frozen') return '冻结中'
  if (s === 'normal') return '正常'
  return s
}

onMounted(() => {
  loadStatus()
  timer = setInterval(tick, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="adapter-widget">
    <div class="widget-header">
      <span>适配器状态</span>
      <Button
        icon="pi pi-refresh"
        size="small"
        severity="secondary"
        text
        :loading="loading"
        @click="loadStatus"
      />
    </div>
    <p v-if="error" class="err-msg">{{ error }}</p>
    <table v-if="adapters.length" class="adapter-table">
      <thead>
        <tr>
          <th>适配器</th>
          <th>状态</th>
          <th>剩余冻结</th>
          <th>冻结次数</th>
          <th>连续失败</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in adapters" :key="a.name">
          <td><strong>{{ a.name.toUpperCase() }}</strong></td>
          <td><Tag :severity="statusSeverity(a.status)" :value="statusLabel(a.status)" /></td>
          <td>{{ a.status === 'frozen' ? `${a.remaining_seconds}s` : '—' }}</td>
          <td>{{ a.freeze_count }}</td>
          <td>{{ a.fail_streak }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="!loading" class="empty">暂无适配器数据</p>
  </div>
</template>

<style scoped>
.adapter-widget {
  height: 100%;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.widget-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--text-heading);
  font-size: 14px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.adapter-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.adapter-table th,
.adapter-table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
}
.adapter-table th {
  font-weight: 600;
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.empty {
  color: var(--text-dim);
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}
.err-msg {
  color: var(--danger);
  font-size: 12px;
  margin: 4px 0;
}
</style>
