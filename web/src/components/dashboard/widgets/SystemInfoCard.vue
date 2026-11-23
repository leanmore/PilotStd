<script setup lang="ts">
defineOptions({ name: 'SystemInfoCard' })
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import { getStats } from '@/api'
import AppLoading from '@/components/ui/AppLoading.vue'

const { t } = useI18n()

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
    dbStatus.value = standardCount.value > 0 ? t('dashboard.common.normal') : t('dashboard.sys_info.db_empty')
    adapterCount.value = (adapterResp.data?.adapters || []).length
  } finally { loading.value = false }
})
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-server" /></div>
        <span class="header-title">{{ t('dashboard.card.sysInfo') }}</span>
      </div>
    </div>

    <AppLoading v-if="loading" variant="skeleton" :rows="3" :label="t('dashboard.common.loading')" />
    <div v-else class="body">
      <div class="version-block">
        <span class="version-label">Current Version</span>
        <span class="version-val">v{{ version }}</span>
      </div>

      <div class="metrics">
        <div class="metric-row">
          <span class="metric-label">{{ t('dashboard.sys_info.db') }}</span>
          <div class="metric-bar"><div class="metric-fill" :class="dbOk ? 'bar-ok' : 'bar-warn'" :style="{ width: dbOk ? '100%' : '30%' }" /></div>
          <span class="metric-status" :class="dbOk ? 'text-ok' : 'text-warn'">{{ dbOk ? t('dashboard.common.normal') : t('dashboard.sys_info.db_empty') }}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">{{ t('dashboard.sys_info.standards') }}</span>
          <div class="metric-bar"><div class="metric-fill bar-ok" style="width: 100%" /></div>
          <span class="metric-status text-ok">{{ t('dashboard.sys_info.count_items', { n: standardCount }) }}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">{{ t('dashboard.sys_info.adapters') }}</span>
          <div class="metric-bar"><div class="metric-fill" :class="adapterOk ? 'bar-ok' : 'bar-warn'" :style="{ width: adapterOk ? '100%' : '60%' }" /></div>
          <span class="metric-status" :class="adapterOk ? 'text-ok' : 'text-warn'">{{ t('dashboard.sys_info.count_online', { n: adapterCount }) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: var(--space-14);
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: var(--space-12);
}
.header-left { display: flex; align-items: center; gap: var(--space-10); }
.header-icon {
  width: 34px; height: var(--icon-tile-md); border-radius: var(--radius-sm); background: var(--success-bg);
  display: flex; align-items: center; justify-content: center; color: var(--success); font-size: var(--font-size-16);
}
.header-title { font-size: var(--font-size-13); font-weight: var(--font-weight-bold); color: var(--text-heading); }

.body { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: var(--space-16); }
.version-block { text-align: center; padding: var(--space-10) 0; }
.version-label { display: block; font-size: var(--font-size-10); color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-4); }
.version-val { font-size: var(--font-size-28); font-weight: var(--font-weight-extrabold); font-family: var(--mono); color: var(--text-heading); }

.metrics { display: flex; flex-direction: column; gap: var(--space-10); }
.metric-row { display: flex; align-items: center; gap: var(--space-10); }
.metric-label { font-size: var(--font-size-11); color: var(--text-dim); width: 48px; flex-shrink: 0; }
/* TODO: [Design Debt] 6px 无精确令牌，暂不替换，待定令牌后统一处理 */
.metric-bar { flex: 1; height: var(--size-6); background: var(--border-light); border-radius: 3px; overflow: hidden; }
.metric-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
.bar-ok { background: var(--success); }
.bar-warn { background: var(--warning); }
.metric-status { font-size: var(--font-size-11); font-weight: var(--font-weight-semibold); min-width: 52px; text-align: right; flex-shrink: 0; }
.text-ok { color: var(--success); }
.text-warn { color: var(--warning); }

.empty { color: var(--text-dim); font-size: var(--font-size-12); text-align: center; flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
