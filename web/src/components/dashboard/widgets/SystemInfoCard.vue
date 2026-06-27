<script setup lang="ts">
// SystemInfoCard.vue — 系统信息 Widget
import { ref, onMounted } from 'vue'
import http from '@/api/http'
import { getStats } from '@/api'

const version = ref('')
const dbStatus = ref('')
const adapterCount = ref(0)
const standardCount = ref(0)
const loading = ref(true)

onMounted(async () => {
  try {
    const [verResp, stats] = await Promise.all([
      http.get('/system/version'),
      getStats(),
    ])
    version.value = verResp.data.version || '—'
    standardCount.value = (stats.current || 0) + (stats.expired || 0) + (stats.pending || 0) + (stats.upcoming || 0)
    dbStatus.value = standardCount.value > 0 ? '正常' : '空库'
    adapterCount.value = 7
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="sysinfo-widget">
    <div class="w-header">
      <span class="w-title">系统信息</span>
    </div>
    <div v-if="loading" class="w-empty">加载中...</div>
    <div v-else class="info-grid">
      <div class="info-item">
        <span class="label">版本</span>
        <code class="value">v{{ version }}</code>
      </div>
      <div class="info-item">
        <span class="label">数据库</span>
        <span class="value" :style="{ color: dbStatus === '正常' ? 'var(--success)' : 'var(--warning)' }">{{ dbStatus }}</span>
      </div>
      <div class="info-item">
        <span class="label">标准总数</span>
        <span class="value">{{ standardCount }}</span>
      </div>
      <div class="info-item">
        <span class="label">适配器</span>
        <span class="value">{{ adapterCount }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sysinfo-widget {
  height: 100%;
  box-sizing: border-box;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}
.w-header { margin-bottom: 10px; }
.w-title { font-weight: 700; color: var(--text-heading); font-size: 15px; }
.w-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-dim); font-size: 13px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; }
.info-item { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; border-bottom: 1px solid var(--border-light); }
.label { color: var(--text-dim); }
.value { font-weight: 600; color: var(--text-heading); }
</style>
