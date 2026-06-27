<script setup lang="ts">
// CacheManager.vue — 缓存管理配置组件
import { ref, onMounted } from 'vue'
import http from '@/api/http'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'

interface CacheStats {
  total_size_mb: number
  max_size_mb: number
  auto_cleanup: boolean
  cleanup_ratio: number
  tables: Record<string, Record<string, number>>
}

const stats = ref<CacheStats>({
  total_size_mb: 0, max_size_mb: 50, auto_cleanup: true, cleanup_ratio: 0.1,
  tables: {},
})
const maxSize = ref(50)
const loading = ref(false)
const cleaned = ref(false)

async function loadStats() {
  try {
    const r = await http.get('/cache/stats')
    stats.value = r.data
    maxSize.value = r.data.max_size_mb
  } catch { /* ignore */ }
}

async function saveConfig() {
  try {
    await http.put('/cache/config', { max_size_mb: maxSize.value })
    await loadStats()
  } catch { /* ignore */ }
}

async function triggerCleanup() {
  loading.value = true
  try {
    await http.post('/cache/cleanup')
    cleaned.value = true
    setTimeout(() => cleaned.value = false, 3000)
    await loadStats()
  } catch { /* ignore */ }
  finally { loading.value = false }
}

/** 汇总各表记录数和状态分布 */
function tableRows(table: string): number {
  const t = stats.value.tables[table] || {}
  return Object.values(t).reduce((a, b) => a + b, 0)
}

function stateCount(state: string): number {
  let total = 0
  for (const t of Object.values(stats.value.tables)) {
    total += t[state] || 0
  }
  return total
}

const sizePercentage = () => {
  if (stats.value.max_size_mb === 0) return 0
  return Math.round((stats.value.total_size_mb / stats.value.max_size_mb) * 100)
}

onMounted(loadStats)
</script>

<template>
  <div>
    <!-- 状态概览 -->
    <div class="cache-stats-bar">
      <div class="stat-block">
        <span class="stat-label">使用量</span>
        <span class="stat-value">{{ stats.total_size_mb.toFixed(1) }} / {{ stats.max_size_mb }} MB</span>
        <ProgressBar :value="sizePercentage()" :style="{ height: '6px' }" />
      </div>
      <div class="stat-block">
        <span class="stat-label">状态</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">
          <Tag severity="success" :value="`有效 ${stateCount('valid')}`" />
          <Tag severity="warn" :value="`失效 ${stateCount('stale')}`" />
          <Tag severity="info" :value="`刷新中 ${stateCount('refresh_pending')}`" />
        </div>
      </div>
    </div>

    <!-- 各表明细 -->
    <div class="table-detail">
      <div v-for="tbl in ['standard_info_cache', 'standard_validity', 'announcement_record']" :key="tbl" class="table-row">
        <span class="tbl-name">{{ tbl }}</span>
        <Tag severity="info" :value="`${tableRows(tbl)} 条`" />
        <span v-if="(stats.tables[tbl] || {}).stale" style="font-size:11px;color:var(--warn);margin-left:4px">
          {{ (stats.tables[tbl] || {}).stale }} 条待刷新
        </span>
      </div>
    </div>

    <!-- 配置 -->
    <div class="cache-config">
      <label style="font-weight:600;font-size:13px;margin-bottom:8px;display:block">缓存大小上限</label>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <label v-for="sz in [50, 100, 200]" :key="sz" style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px">
          <input type="radio" :value="sz" v-model="maxSize" @change="saveConfig" />
          {{ sz }} MB
        </label>
      </div>

      <div class="actions">
        <Button label="立即清理" icon="pi pi-trash" size="small" severity="warn" :loading="loading" @click="triggerCleanup" />
        <Button label="刷新统计" icon="pi pi-refresh" size="small" severity="secondary" outlined @click="loadStats" />
        <span v-if="cleaned" style="color:var(--success);font-size:12px">清理完成</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cache-stats-bar { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; }
.stat-block { flex: 1; min-width: 180px; }
.stat-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.03em; }
.stat-value { font-size: 14px; font-weight: 600; display: block; margin: 2px 0 4px; }
.table-detail { margin-bottom: 16px; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 14px; }
.table-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.table-row + .table-row { border-top: 1px solid var(--border-light); }
.tbl-name { font-size: 12px; font-family: monospace; color: var(--text); flex: 1; }
.cache-config { border-top: 1px solid var(--border); padding-top: 12px; }
.actions { display: flex; align-items: center; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
</style>
