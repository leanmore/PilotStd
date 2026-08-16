<script setup lang="ts">
defineOptions({ name: 'SchedulerStatus' })
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { getSchedulerStatus } from '@/api/scheduler'
import type { RouteTag } from '@/types/route-tag'

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
    console.error('获取调度器状态失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchStatus('/scheduler'))
</script>

<template>
  <div class="page">
    <h2 class="page-title">调度器状态</h2>
    <Card>
      <template #content>
        <div class="status-header">
          <Badge :value="status.running ? '运行中' : '已停止'" :severity="status.running ? 'success' : 'danger'" />
          <span class="text-sm">任务数: {{ status.job_count }}</span>
          <span class="text-sm">更新: {{ formatTime(status.timestamp) }}</span>
          <Button icon="pi pi-refresh" text size="small" @click="fetchStatus()" />
        </div>
        <DataTable :value="status.jobs" striped-rows size="small" :loading="loading">
          <Column field="id" header="任务 ID" />
          <Column header="下次执行">
            <template #body="{ data }">
              {{ data.next_run_time ? formatTime(data.next_run_time) : '-' }}
            </template>
          </Column>
          <Column field="trigger" header="触发器" />
          <Column header="状态">
            <template #body="{ data }">
              <Badge :value="data.pending ? '等待中' : '已调度'" :severity="data.pending ? 'warn' : 'info'" />
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.status-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px; gap: 12px; flex-wrap: wrap;
}
.text-sm { font-size: 13px; color: var(--text-color-secondary); }
</style>
