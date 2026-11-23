<script setup lang="ts">
defineOptions({ name: 'SchedulerStatus' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Column from 'primevue/column'
import { getSchedulerStatus } from '@/api/scheduler'
import type { RouteTag } from '@/types/route-tag'
import AppButton from '@/components/ui/AppButton.vue'
import AppTable from '@/components/ui/AppTable.vue'
import PageContainer from '@/components/ui/PageContainer.vue'
import AppCard from '@/components/ui/AppCard.vue'

interface Job {
  id: string
  next_run_time: string | null
  trigger: string
  pending: boolean
}

interface SchedulerStatus {
  running: boolean
  job_count: number
  jobs: Job[]
  timestamp: string
}

const { t } = useI18n()

const status = ref<SchedulerStatus>({ running: false, job_count: 0, jobs: [], timestamp: '' })
const loading = ref(false)

const formatTime = (iso: string) => {
  return new Date(iso).toLocaleString('zh-CN')
}

const fetchStatus = async (routeTag?: RouteTag) => {
  loading.value = true
  try {
    const resp = await getSchedulerStatus(routeTag ? { routeTag } : undefined)
    status.value = resp.data
  } catch (e) {
    console.error('获取调度器状态失败:', e) // i18n-allow: 开发者日志：调度器状态获取失败
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchStatus('/scheduler'))
</script>

<template>
  <PageContainer :max-width="1100" :title="t('scheduler.title')">
    <AppCard>
      <template #content>
        <div class="status-header">
          <Badge :value="status.running ? t('scheduler.running') : t('scheduler.stopped')" :severity="status.running ? 'success' : 'danger'" />
          <span class="text-sm">{{ t('scheduler.job_count', { n: status.job_count }) }}</span>
          <span class="text-sm">{{ t('scheduler.updated', { time: formatTime(status.timestamp) }) }}</span>
          <AppButton
            icon="pi pi-refresh"
            @click="fetchStatus()"
            size="s"
            type="ghost"
          />
        </div>
        <AppTable :value="status.jobs" striped-rows size="small" :loading="loading">
          <Column field="id" :header="t('scheduler.col_job_id')" />
          <Column :header="t('scheduler.col_next_run')">
            <template #body="{ data }">
              {{ data.next_run_time ? formatTime(data.next_run_time) : '-' }}
            </template>
          </Column>
          <Column field="trigger" :header="t('scheduler.col_trigger')" />
          <Column :header="t('scheduler.col_status')">
            <template #body="{ data }">
              <Badge :value="data.pending ? t('scheduler.pending') : t('scheduler.scheduled')" :severity="data.pending ? 'warn' : 'info'" />
            </template>
          </Column>
        </AppTable>
      </template>
    </AppCard>
  </PageContainer>
</template>

<style scoped>
.status-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: var(--space-16); gap: var(--space-12); flex-wrap: wrap;
}
.text-sm { font-size: var(--font-size-13); color: var(--text-secondary); }
</style>
