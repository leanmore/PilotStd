<script setup lang="ts">
// TaskManager.vue — 任务队列管理界面
import { ref, onMounted } from 'vue'
import http from '@/api/http'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Dialog from 'primevue/dialog'
import SelectButton from 'primevue/selectbutton'

interface TaskItem {
  task_id: string
  task_type: string
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  retry_count: number
  max_retries: number
  queue_name: string
  error_log: string
  result_json: string
  created_at: string
  started_at: string
  finished_at: string
}

const tasks = ref<TaskItem[]>([])
const total = ref(0)
const page = ref(0)
const filter = ref('')
const loading = ref(false)
const detailTask = ref<TaskItem | null>(null)

const statusOptions = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已失败', value: 'failed' },
]

async function loadTasks() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value + 1, page_size: 30 }
    if (filter.value) params.status = filter.value
    const r = await http.get('/tasks', { params })
    tasks.value = r.data.items
    total.value = r.data.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

function getStatusSeverity(s: string): 'success' | 'danger' | 'info' | 'warn' | 'secondary' {
  const map: Record<string, 'success' | 'danger' | 'info' | 'warn' | 'secondary'> = {
    completed: 'success', failed: 'danger', running: 'info',
    pending: 'warn', cancelled: 'secondary', paused: 'warn',
  }
  return map[s] || 'secondary'
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '待处理', running: '运行中', completed: '已完成',
    failed: '失败', cancelled: '已取消', paused: '已暂停',
  }
  return map[s] || s
}

function progress(task: TaskItem): number {
  if (task.total_items === 0) return task.status === 'completed' ? 100 : 0
  return Math.round((task.completed_items / task.total_items) * 100)
}

async function retryTask(taskId: string) {
  try { await http.post(`/tasks/${taskId}/retry`); await loadTasks() } catch { /* ignore */ }
}

async function cancelTask(taskId: string) {
  try { await http.post(`/tasks/${taskId}/cancel`); await loadTasks() } catch { /* ignore */ }
}

function showDetail(task: TaskItem) { detailTask.value = task }

onMounted(loadTasks)
</script>

<template>
  <div>
    <div class="toolbar">
      <SelectButton v-model="filter" :options="statusOptions" option-label="label" option-value="value" size="small" @change="loadTasks" />
      <Button label="刷新" icon="pi pi-refresh" size="small" severity="secondary" outlined :loading="loading" @click="loadTasks" />
      <span style="font-size:12px;color:var(--text-dim);margin-left:auto">共 {{ total }} 条</span>
    </div>

    <DataTable :value="tasks" striped-rows size="small" class="mt-2" paginator :rows="30" :total-records="total" @page="page = $event.page; loadTasks()">
      <Column field="task_id" header="任务ID" style="min-width:130px">
        <template #body="{ data }"><code style="font-size:11px">{{ data.task_id.slice(0, 12) }}</code></template>
      </Column>
      <Column field="task_type" header="类型" style="min-width:80px">
        <template #body="{ data }">
          <Tag severity="info" :value="data.task_type" />
        </template>
      </Column>
      <Column header="状态" style="min-width:70px">
        <template #body="{ data }">
          <Tag :severity="getStatusSeverity(data.status)" :value="statusLabel(data.status)" />
        </template>
      </Column>
      <Column header="进度" style="min-width:120px">
        <template #body="{ data }">
          <ProgressBar :value="progress(data)" :style="{ height: '6px' }" v-if="data.total_items > 0" />
          <span v-else style="font-size:12px;color:var(--text-dim)">--</span>
        </template>
      </Column>
      <Column field="queue_name" header="队列" style="min-width:60px">
        <template #body="{ data }"><span style="font-size:12px">{{ data.queue_name }}</span></template>
      </Column>
      <Column field="created_at" header="创建时间" style="min-width:130px">
        <template #body="{ data }"><span style="font-size:11px">{{ data.created_at.slice(0, 19) }}</span></template>
      </Column>
      <Column header="操作" style="min-width:90px">
        <template #body="{ data }">
          <div style="display:flex;gap:4px">
            <Button icon="pi pi-refresh" v-if="data.status === 'failed'" size="small" text rounded severity="warn" @click="retryTask(data.task_id)" />
            <Button icon="pi pi-times" v-if="data.status === 'running'" size="small" text rounded severity="danger" @click="cancelTask(data.task_id)" />
            <Button icon="pi pi-info-circle" size="small" text rounded @click="showDetail(data)" />
          </div>
        </template>
      </Column>
    </DataTable>

    <Dialog :visible="!!detailTask" header="任务详情" :modal="true" :style="{ width: '500px' }" @hide="detailTask = null">
      <div v-if="detailTask" style="font-size:13px">
        <p><strong>任务ID:</strong> {{ detailTask.task_id }}</p>
        <p><strong>类型:</strong> {{ detailTask.task_type }}</p>
        <p><strong>状态:</strong> {{ statusLabel(detailTask.status) }}</p>
        <p><strong>重试:</strong> {{ detailTask.retry_count }}/{{ detailTask.max_retries }}</p>
        <p><strong>创建:</strong> {{ detailTask.created_at }}</p>
        <p v-if="detailTask.started_at"><strong>开始:</strong> {{ detailTask.started_at }}</p>
        <p v-if="detailTask.finished_at"><strong>完成:</strong> {{ detailTask.finished_at }}</p>
        <div v-if="detailTask.error_log" style="margin-top:8px;padding:8px;background:var(--surface);border-radius:4px">
          <strong style="color:var(--danger)">错误:</strong>
          <pre style="font-size:11px;white-space:pre-wrap;margin:4px 0">{{ detailTask.error_log }}</pre>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
</style>
