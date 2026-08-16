<script setup lang="ts">
defineOptions({ name: 'SystemInfoCard' })
import { ref, onMounted, computed } from 'vue'
import http from '@/api/http'
import { getStats } from '@/api'

const version = ref('')
const standardCount = ref(0)
const dbStatus = ref('')
const adapterCount = ref(0)
const loading = ref(true)

const dbOk = computed(() => standardCount.value > 0)
const adapterOk = computed(() => adapterCount.value > 0)

onMounted(async () => {
  try {
    const [verResp, stats, adapterResp] = await Promise.all([
      http.get('/system/version', { routeTag: '/' }),
      getStats('/'),
      http.get('/adapter/status', { params: { type: 'query' }, routeTag: '/' }),
    ])
    version.value = verResp.data.version || '—'
    standardCount.value = (stats.current || 0) + (stats.expired || 0) + (stats.pending || 0) + (stats.upcoming || 0)
    dbStatus.value = standardCount.value > 0 ? '正常' : '空库'
    adapterCount.value = (adapterResp.data?.adapters || []).length
  } finally { loading.value = false }
})
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-server" /></div>
        <span class="header-title">系统状态</span>
      </div>
    </div>

    <div v-if="loading" class="empty">加载中...</div>
    <div v-else class="body">
      <div class="version-block">
        <span class="version-label">Current Version</span>
        <span class="version-val">v{{ version }}</span>
      </div>

      <div class="metrics">
        <div class="metric-row">
          <span class="metric-label">数据库</span>
          <div class="metric-bar"><div class="metric-fill" :class="dbOk ? 'bar-ok' : 'bar-warn'" :style="{ width: dbOk ? '100%' : '30%' }" /></div>
          <span class="metric-status" :class="dbOk ? 'text-ok' : 'text-warn'">{{ dbOk ? '正常' : '空库' }}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">标准库</span>
          <div class="metric-bar"><div class="metric-fill bar-ok" style="width: 100%" /></div>
          <span class="metric-status text-ok">{{ standardCount }} 条</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">适配器</span>
          <div class="metric-bar"><div class="metric-fill" :class="adapterOk ? 'bar-ok' : 'bar-warn'" :style="{ width: adapterOk ? '100%' : '60%' }" /></div>
          <span class="metric-status" :class="adapterOk ? 'text-ok' : 'text-warn'">{{ adapterCount }} 在线</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: 14px;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: 12px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon {
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(34,197,94,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--success); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }

.body { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 16px; }
.version-block { text-align: center; padding: 10px 0; }
.version-label { display: block; font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
.version-val { font-size: 28px; font-weight: 800; font-family: var(--mono); color: var(--text-heading); }

.metrics { display: flex; flex-direction: column; gap: 10px; }
.metric-row { display: flex; align-items: center; gap: 10px; }
.metric-label { font-size: 11px; color: var(--text-dim); width: 48px; flex-shrink: 0; }
.metric-bar { flex: 1; height: 6px; background: var(--border-light); border-radius: 3px; overflow: hidden; }
.metric-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
.bar-ok { background: var(--success); }
.bar-warn { background: var(--warning); }
.metric-status { font-size: 11px; font-weight: 600; min-width: 52px; text-align: right; flex-shrink: 0; }
.text-ok { color: var(--success); }
.text-warn { color: var(--warning); }

.empty { color: var(--text-dim); font-size: 12px; text-align: center; flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
