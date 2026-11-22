<script setup lang="ts">
defineOptions({ name: 'CacheManager' })
// CacheManager.vue — 缓存管理配置组件
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()

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
    const r = await http.get('/cache/stats', { routeTag: '/settings' })
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
        <span class="stat-label">{{ t('settings.cache.usage') }}</span>
        <span class="stat-value">{{ stats.total_size_mb.toFixed(1) }} / {{ stats.max_size_mb }} MB</span>
        <ProgressBar :value="sizePercentage()" :style="{ height: '6px' }" />
      </div>
      <div class="stat-block">
        <span class="stat-label">{{ t('settings.cache.status') }}</span>
        <div style="display:flex;gap:var(--space-6);flex-wrap:wrap;margin-top:var(--space-4)">
          <Tag severity="success" :value="t('settings.cache.valid', { n: stateCount('valid') })" />
          <Tag severity="warn" :value="t('settings.cache.stale', { n: stateCount('stale') })" />
          <Tag severity="info" :value="t('settings.cache.refreshing', { n: stateCount('refresh_pending') })" />
        </div>
      </div>
    </div>

    <!-- 各表明细 -->
    <div class="table-detail">
      <div v-for="tbl in ['standard_info_cache', 'standard_validity', 'announcement_record']" :key="tbl" class="table-row">
        <span class="tbl-name">{{ tbl }}</span>
        <Tag severity="info" :value="t('settings.cache.rows', { n: tableRows(tbl) })" />
        <span v-if="(stats.tables[tbl] || {}).stale" style="font-size:var(--font-size-11);color:var(--warning);margin-left:var(--space-4)">
          {{ t('settings.cache.stale_rows', { n: (stats.tables[tbl] || {}).stale }) }}
        </span>
      </div>
    </div>

    <!-- 配置 -->
    <div class="cache-config">
      <label style="font-weight:var(--font-weight-semibold);font-size:var(--font-size-13);margin-bottom:var(--space-8);display:block">{{ t('settings.cache.max_size') }}</label>
      <div style="display:flex;gap:var(--space-12);flex-wrap:wrap">
        <label v-for="sz in [50, 100, 200]" :key="sz" style="display:flex;align-items:center;gap:var(--space-4);cursor:pointer;font-size:var(--font-size-13)">
          <input type="radio" :value="sz" v-model="maxSize" @change="saveConfig" />
          {{ sz }} MB
        </label>
      </div>

      <div class="actions">
        <AppButton
        :label="t('settings.cache.cleanup_now')"
        icon="pi pi-trash"
        size="s"
        type="danger"
        :loading="loading"
        @click="triggerCleanup"
      />
<AppButton
          :label="t('settings.cache.refresh_stats')"
          icon="pi pi-refresh"
          @click="loadStats"
          size="s"
          type="secondary"
          outlined
        />
        <span v-if="cleaned" style="color:var(--success);font-size:var(--font-size-12)">{{ t('settings.cache.cleaned') }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cache-stats-bar { display: flex; gap: var(--space-20); flex-wrap: wrap; margin-bottom: var(--space-16); }
.stat-block { flex: 1; min-width: 180px; }
.stat-label { font-size: var(--font-size-11); color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.03em; }
.stat-value { font-size: var(--font-size-14); font-weight: var(--font-weight-semibold); display: block; margin: var(--space-2) 0 var(--space-4); }
.table-detail { margin-bottom: var(--space-16); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: var(--space-10) var(--space-14); }
.table-row { display: flex; align-items: center; gap: var(--space-8); padding: var(--space-4) 0; }
.table-row + .table-row { border-top: 1px solid var(--border-light); }
.tbl-name { font-size: var(--font-size-12); font-family: monospace; color: var(--text); flex: 1; }
.cache-config { border-top: 1px solid var(--border); padding-top: var(--space-12); }
.actions { display: flex; align-items: center; gap: var(--space-8); margin-top: var(--space-12); flex-wrap: wrap; }
</style>
