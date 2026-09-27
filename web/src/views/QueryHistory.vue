<script setup lang="ts">
defineOptions({ name: 'QueryHistory' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import { getQueryResults } from '@/api'
import type { RouteTag } from '@/types/route-tag'

const { t } = useI18n()

interface QueryResult { standard_number: string; status: string; found_name?: string; source_site?: string }
const results = ref<QueryResult[]>([])
const loading = ref(false)

const fetchHistory = async (routeTag?: RouteTag) => {
  loading.value = true
  try {
    const resp = await getQueryResults(routeTag ? { routeTag } : undefined)
    results.value = resp.data.results || []
  } catch { /* ignore */ } finally { loading.value = false }
}

onMounted(() => fetchHistory('/query-history'))
</script>

<template>
  <div class="page">
    <h2 class="page-title">{{ t('query_history.title') }}</h2>
    <Card>
      <template #content>
        <div class="header-row">
          <span class="text-sm" v-if="results.length">{{ t('query_history.total', { n: results.length }) }}</span>
          <Button icon="pi pi-refresh" text size="small" @click="fetchHistory()" />
        </div>
        <table v-if="results.length" class="data-table">
          <thead><tr><th>{{ t('standard_table.col_standard_number') }}</th><th>{{ t('standard_table.col_status') }}</th><th>{{ t('standard_table.col_name') }}</th><th>{{ t('standard_table.col_source') }}</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in results" :key="i">
              <td>{{ r.standard_number }}</td>
              <!-- i18n-allow: 与后端返回的中文状态值比较（决定标签颜色），翻译即失效 -->
              <td><Tag :value="r.status" :severity="r.status === '现行' ? 'success' : 'warn'" /></td>
              <td>{{ r.found_name || '-' }}</td>
              <td>{{ r.source_site || '-' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="!loading" class="empty">{{ t('query_history.empty') }}</p>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 900px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.text-sm { font-size: 13px; color: var(--text-color-secondary); }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.data-table th { font-weight: 600; color: var(--text-secondary); }
.empty { padding: 32px 0; text-align: center; color: var(--text-color-secondary); }
</style>
