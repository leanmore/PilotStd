<script setup lang="ts">
defineOptions({ name: 'QueryHistory' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import { getQueryResults } from '@/api'
import { isActiveStatusKey } from '@/utils/stdStatus'
import type { RouteTag } from '@/types/route-tag'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()

interface QueryResult {
  standard_number: string
  status: string
  /** 后端 status_key 契约：稳定英文键（active/withdrawn/…），前端只比较它 */
  status_key?: string
  found_name?: string
  source_site?: string
}
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
          <AppButton
            icon="pi pi-refresh"
            @click="fetchHistory()"
            size="s"
            type="ghost"
          />
        </div>
        <table v-if="results.length" class="data-table">
          <thead><tr><th>{{ t('standard_table.col_standard_number') }}</th><th>{{ t('standard_table.col_status') }}</th><th>{{ t('standard_table.col_name') }}</th><th>{{ t('standard_table.col_source') }}</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in results" :key="i">
              <td>{{ r.standard_number }}</td>
              <!-- 只比较后端给的英文键 status_key（#32-C / R14-4c），与界面语言无关 -->
              <td><Tag :value="r.status" :severity="isActiveStatusKey(r.status_key) ? 'success' : 'warn'" /></td>
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
.page-title { margin: 0 0 var(--space-20); font-size: var(--font-size-20); font-weight: var(--font-weight-semibold); color: var(--text-heading); }
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-12); }
.text-sm { font-size: var(--font-size-13); color: var(--text-secondary); }
.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-13); }
.data-table th, .data-table td { padding: var(--space-8) var(--space-12); text-align: left; border-bottom: 1px solid var(--border); }
.data-table th { font-weight: var(--font-weight-semibold); color: var(--text-secondary); }
.empty { padding: var(--space-32) 0; text-align: center; color: var(--text-secondary); }
</style>
