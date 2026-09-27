<script setup lang="ts">
defineOptions({ name: 'TaskManager' })
// TaskManager.vue — 任务队列管理界面
import { useI18n } from 'vue-i18n'
import { ref, computed, onMounted } from 'vue'
import http from '@/api/http'
import { getItem, setItem } from '@/lib/storage'
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

const { t } = useI18n()

const tasks = ref<TaskItem[]>([])
const total = ref(0)
const page = ref(Number(getItem('taskmgr_page')) || 0)
const filter = ref('')

function onPage(e: { page: number }) {
  page.value = e.page
  setItem('taskmgr_page', String(e.page))
  loadTasks()
}
const loading = ref(false)
const detailTask = ref<TaskItem | null>(null)

const statusOptions = computed(() => [
  { label: t('task.manager.filter_all'), value: '' },
  { label: t('task.manager.status.pending'), value: 'pending' },
  { label: t('task.manager.status.running'), value: 'running' },
  { label: t('task.manager.status.completed'), value: 'completed' },
  { label: t('task.manager.filter_failed'), value: 'failed' },
])

async function loadTasks() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value + 1, page_size: 30 }
    if (filter.value) params.status = filter.value
    const r = await http.get('/tasks', { params, routeTag: '/settings' })
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
    pending: t('task.manager.status.pending'), running: t('task.manager.status.running'),
    completed: t('task.manager.status.completed'), failed: t('task.manager.status.failed'),
    cancelled: t('task.manager.status.cancelled'), paused: t('task.manager.status.paused'),
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

// ── 管道历史 ──
const subTab = ref<'tasks' | 'runs'>('tasks')
interface PipelineRunItem {
  run_id: string; current_step: string; status: string; progress: number
  error_message: string; created_at: string; updated_at: string
}
const runs = ref<PipelineRunItem[]>([])
const runsTotal = ref(0)
const runsPage = ref(0)
const runsLoading = ref(false)

async function loadPipelineRuns() {
  runsLoading.value = true
  try {
    const r = await http.get('/tasks/runs', { params: { page: runsPage.value + 1, page_size: 20 } })
    runs.value = r.data.items; runsTotal.value = r.data.total
  } catch { /* ignore */ }
  finally { runsLoading.value = false }
}

function onRunsPage(e: { page: number }) { runsPage.value = e.page; loadPipelineRuns() }

function stepLabel(s: string) {
  const map: Record<string, string> = { scan: t('task.step.scan'), query: t('task.step.query'), download: t('task.step.download'), normalize: t('task.step.normalize'), archive: t('task.step.archive') }
  return map[s] || s
}
</script>

<template>
  <div>
    <!-- 子Tab切换 -->
    <div style="display:flex;gap:0;margin-bottom:8px;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;width:fit-content">
      <button :class="['subtab', { active: subTab === 'tasks' }]" @click="subTab = 'tasks'; loadTasks()">{{ t('task.manager.tab_tasks') }}</button>
      <button :class="['subtab', { active: subTab === 'runs' }]" @click="subTab = 'runs'; loadPipelineRuns()">{{ t('task.manager.tab_runs') }}</button>
    </div>

    <!-- 后台任务 -->
    <template v-if="subTab === 'tasks'">
    <div class="toolbar">
      <SelectButton v-model="filter" :options="statusOptions" option-label="label" option-value="value" size="small" @change="loadTasks" />
      <Button :label="t('task.manager.refresh')" icon="pi pi-refresh" size="small" severity="secondary" outlined :loading="loading" @click="loadTasks" />
      <span style="font-size:12px;color:var(--text-dim);margin-left:auto">{{ t('task.manager.total', { n: total }) }}</span>
    </div>

    <DataTable :value="tasks" striped-rows size="small" class="mt-2" paginator :rows="30" :total-records="total" @page="onPage">
      <Column field="task_id" :header="t('task.manager.col_task_id')" style="min-width:130px">
        <template #body="{ data }"><code style="font-size:11px">{{ data.task_id.slice(0, 12) }}</code></template>
      </Column>
      <Column field="task_type" :header="t('task.manager.col_type')" style="min-width:80px">
        <template #body="{ data }">
          <Tag severity="info" :value="data.task_type" />
        </template>
      </Column>
      <Column :header="t('task.manager.col_status')" style="min-width:70px">
        <template #body="{ data }">
          <Tag :severity="getStatusSeverity(data.status)" :value="statusLabel(data.status)" />
        </template>
      </Column>
      <Column :header="t('task.manager.col_progress')" style="min-width:120px">
        <template #body="{ data }">
          <ProgressBar :value="progress(data)" :style="{ height: '6px' }" v-if="data.total_items > 0" />
          <span v-else style="font-size:12px;color:var(--text-dim)">--</span>
        </template>
      </Column>
      <Column field="queue_name" :header="t('task.manager.col_queue')" style="min-width:60px">
        <template #body="{ data }"><span style="font-size:12px">{{ data.queue_name }}</span></template>
      </Column>
      <Column field="created_at" :header="t('task.manager.col_created')" style="min-width:130px">
        <template #body="{ data }"><span style="font-size:11px">{{ data.created_at.slice(0, 19) }}</span></template>
      </Column>
      <Column :header="t('task.manager.col_action')" style="min-width:90px">
        <template #body="{ data }">
          <div style="display:flex;gap:4px">
            <Button icon="pi pi-refresh" v-if="data.status === 'failed'" size="small" text rounded severity="warn" @click="retryTask(data.task_id)" />
            <Button icon="pi pi-times" v-if="data.status === 'running'" size="small" text rounded severity="danger" @click="cancelTask(data.task_id)" />
            <Button icon="pi pi-info-circle" size="small" text rounded @click="showDetail(data)" />
          </div>
        </template>
      </Column>
    </DataTable>

    <Dialog :visible="!!detailTask" :header="t('task.manager.detail_title')" :modal="true" :style="{ width: '500px' }" @hide="detailTask = null">
      <div v-if="detailTask" style="font-size:13px">
        <p><strong>{{ t('task.manager.field_task_id') }}</strong> {{ detailTask.task_id }}</p>
        <p><strong>{{ t('task.manager.field_type') }}</strong> {{ detailTask.task_type }}</p>
        <p><strong>{{ t('task.manager.field_status') }}</strong> {{ statusLabel(detailTask.status) }}</p>
        <p><strong>{{ t('task.manager.field_retry') }}</strong> {{ detailTask.retry_count }}/{{ detailTask.max_retries }}</p>
        <p><strong>{{ t('task.manager.field_created') }}</strong> {{ detailTask.created_at }}</p>
        <p v-if="detailTask.started_at"><strong>{{ t('task.manager.field_started') }}</strong> {{ detailTask.started_at }}</p>
        <p v-if="detailTask.finished_at"><strong>{{ t('task.manager.field_finished') }}</strong> {{ detailTask.finished_at }}</p>
        <div v-if="detailTask.error_log" style="margin-top:8px;padding:8px;background:var(--surface);border-radius:4px">
          <strong style="color:var(--danger)">{{ t('task.manager.field_error') }}</strong>
          <pre style="font-size:11px;white-space:pre-wrap;margin:4px 0">{{ detailTask.error_log }}</pre>
        </div>
      </div>
    </Dialog>
    </template>

    <!-- 管道历史 -->
    <template v-if="subTab === 'runs'">
      <div class="toolbar">
        <Button :label="t('task.manager.refresh')" icon="pi pi-refresh" size="small" severity="secondary" outlined :loading="runsLoading" @click="loadPipelineRuns" />
        <span style="font-size:12px;color:var(--text-dim);margin-left:auto">{{ t('task.manager.total', { n: runsTotal }) }}</span>
      </div>
      <DataTable :value="runs" striped-rows size="small" class="mt-2" paginator :rows="20" :total-records="runsTotal" @page="onRunsPage">
        <Column field="run_id" header="Run ID" style="min-width:130px">
          <template #body="{ data }"><code style="font-size:11px">{{ data.run_id.slice(0, 12) }}</code></template>
        </Column>
        <Column :header="t('task.manager.col_stage')" style="min-width:80px">
          <template #body="{ data }"><Tag severity="info" :value="stepLabel(data.current_step)" /></template>
        </Column>
        <Column :header="t('task.manager.col_status')" style="min-width:70px">
          <template #body="{ data }">
            <Tag :severity="getStatusSeverity(data.status)" :value="statusLabel(data.status)" />
          </template>
        </Column>
        <Column :header="t('task.manager.col_progress')" style="min-width:100px">
          <template #body="{ data }">
            <ProgressBar :value="data.progress" :style="{ height: '6px' }" />
          </template>
        </Column>
        <Column field="created_at" :header="t('task.manager.col_created')" style="min-width:130px">
          <template #body="{ data }"><span style="font-size:11px">{{ (data.created_at || '').slice(0, 19) }}</span></template>
        </Column>
        <Column field="error_message" :header="t('task.manager.col_error')" style="min-width:100px">
          <template #body="{ data }">
            <span v-if="data.error_message" style="font-size:11px;color:var(--danger)">{{ data.error_message.slice(0, 50) }}</span>
            <span v-else style="font-size:11px;color:var(--text-dim)">--</span>
          </template>
        </Column>
      </DataTable>
    </template>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.subtab { padding: 6px 14px; border: none; background: none; color: var(--text-dim); cursor: pointer; font-size: 12px; border-right: 1px solid var(--border); }
.subtab:last-child { border-right: none; }
.subtab.active { background: var(--primary-bg); color: var(--primary); font-weight: 600; }
</style>
