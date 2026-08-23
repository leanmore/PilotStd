<script setup lang="ts">
defineOptions({ name: 'DownloadQueue' })
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import { getTasks, cancelTask as cancelTaskApi } from '@/api/tasks'
import type { RouteTag } from '@/types/route-tag'

interface Task { task_id: string; task_type: string; status: string; total_items: number; created_at: string }
const tasks = ref<Task[]>([])
const loading = ref(false)

const fetchTasks = async (routeTag?: RouteTag) => {
  loading.value = true
  try {
    const resp = await getTasks(routeTag ? { routeTag } : undefined)
    tasks.value = resp.data.items || []
  } catch { /* ignore */ } finally { loading.value = false }
}

const cancelTask = async (id: string) => {
  try {
    await cancelTaskApi(id)
    fetchTasks('/download-queue')
  } catch { /* ignore */ }
}

onMounted(() => fetchTasks('/download-queue'))
</script>

<template>
  <div class="page">
    <h2 class="page-title">下载队列</h2>
    <Card>
      <template #content>
        <div class="header-row">
          <span class="text-sm" v-if="tasks.length">共 {{ tasks.length }} 个任务</span>
          <Button icon="pi pi-refresh" text size="small" @click="fetchTasks()" />
        </div>
        <table v-if="tasks.length" class="data-table">
          <thead><tr><th>任务ID</th><th>类型</th><th>状态</th><th>条目</th><th>创建时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.task_id">
              <td>{{ t.task_id }}</td>
              <td>{{ t.task_type }}</td>
              <td><Tag :value="t.status" :severity="t.status === 'running' ? 'info' : t.status === 'completed' ? 'success' : 'warn'" /></td>
              <td>{{ t.total_items }}</td>
              <td>{{ new Date(t.created_at).toLocaleString('zh-CN') }}</td>
              <td>
                <Button v-if="t.status === 'running'" icon="pi pi-times" text size="small" severity="danger" @click="cancelTask(t.task_id)" />
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="!loading" class="empty">暂无队列任务</p>
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
