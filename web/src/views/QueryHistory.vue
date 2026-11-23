<script setup lang="ts">
defineOptions({ name: 'QueryHistory' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import { getQueryResults } from '@/api'
import { isActiveStatusKey } from '@/utils/stdStatus'
import type { RouteTag } from '@/types/route-tag'
import AppTable from '@/components/ui/AppTable.vue'
import Column from 'primevue/column'
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
        <AppTable v-if="results.length" :value="results" size="small">
          <Column field="standard_number" :header="t('standard_table.col_standard_number')" />
          <!-- 只比较后端给的英文键 status_key（#32-C / R14-4c），与界面语言无关 -->
          <Column :header="t('standard_table.col_status')">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="isActiveStatusKey(data.status_key) ? 'success' : 'warn'" />
            </template>
          </Column>
          <Column :header="t('standard_table.col_name')">
            <template #body="{ data }">{{ data.found_name || '-' }}</template>
          </Column>
          <Column :header="t('standard_table.col_source')">
            <template #body="{ data }">{{ data.source_site || '-' }}</template>
          </Column>
        </AppTable>
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
.empty { padding: var(--space-32) 0; text-align: center; color: var(--text-secondary); }
</style>
