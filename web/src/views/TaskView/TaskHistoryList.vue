<script setup lang="ts">
defineOptions({ name: 'TaskHistoryList' })
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import { TASK_HISTORY_PAGE_SIZES } from '@/utils/pagination'
import type { TaskRecord } from './types'

const props = defineProps<{
  history: TaskRecord[]
  page: number
  rows: number
}>()

const emit = defineEmits<{
  page: [event: { page: number; rows: number }]
  view: [record: TaskRecord]
  rerun: [record: TaskRecord]
  delete: [record: TaskRecord]
}>()

const { t } = useI18n()

const paginatedHistory = computed(() => {
  const start = props.page * props.rows
  return props.history.slice(start, start + props.rows)
})

function statusSeverity(s: string) {
  if (s === 'success') return 'success'
  if (s === 'partial' || s === 'stopped') return 'warn'
  return 'danger'
}
function statusLabel(s: string) {
  if (s === 'success') return t('task.status.done')
  if (s === 'partial') return t('task.status.partial')
  if (s === 'stopped') return t('task.status.stopped')
  return t('task.status.failed')
}
</script>

<template>
  <div v-if="history.length" class="card mt-3">
    <div class="card-header">{{ t('task.history_title') }}</div>
    <DataView :value="paginatedHistory" size="small">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.id" class="p-2 border-bottom">
          <div class="flex" style="display:flex;gap:12px;align-items:center;padding:6px 0;border-bottom:1px solid var(--border-light)">
            <div style="flex:1;min-width:0">
              <div class="flex" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
                <span class="text-mono" style="font-size:13px;font-family:var(--mono)">{{ item.time }}</span>
                <span class="text-dim" style="font-size:12px;color:var(--text-dim)">{{ item.path }}</span>
              </div>
              <div class="flex" style="display:flex;gap:12px;font-size:12px;color:var(--text-dim);margin-top:4px">
                <span>{{ t('task.history_scan', { n: item.scanCount }) }}</span>
                <span>{{ t('task.history_query', { n: item.queryFound }) }}</span>
                <span>{{ t('task.history_download', { n: item.dlSuccess }) }}</span>
              </div>
            </div>
            <div class="flex" style="display:flex;gap:6px;align-items:center">
              <Tag :value="statusLabel(item.status)" :severity="statusSeverity(item.status)" />
              <Button :label="t('task.detail')" size="small" text @click="emit('view', item)" />
              <Button :label="t('task.rerun')" size="small" text severity="info" @click="emit('rerun', item)" />
              <Button :label="t('task.delete')" size="small" text severity="danger" @click="emit('delete', item)" />
            </div>
          </div>
        </div>
      </template>
    </DataView>
    <Paginator :rows="rows" :rowsPerPageOptions="TASK_HISTORY_PAGE_SIZES" :totalRecords="history.length" @page="emit('page', $event)" class="mt-2" />
  </div>
</template>

<style scoped>
.mt-2 { margin-top: 12px; }
.mt-3 { margin-top: 16px; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
.text-dim { color: var(--text-dim, #6b7280); }
.text-mono { font-family: var(--mono, 'Consolas', 'Courier New', monospace); }
</style>
