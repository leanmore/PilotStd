<script setup lang="ts">
defineOptions({ name: 'DownloadQueue' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { getTasks, cancelTask as cancelTaskApi } from '@/api/tasks'
import type { RouteTag } from '@/types/route-tag'
import AppTable from '@/components/ui/AppTable.vue'
import AppButton from '@/components/ui/AppButton.vue'
import PageContainer from '@/components/ui/PageContainer.vue'
import AppCard from '@/components/ui/AppCard.vue'

interface Task { task_id: string; task_type: string; status: string; total_items: number; created_at: string }
const { t } = useI18n()
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
  <PageContainer :max-width="900" :title="t('download.queue.title')">
    <AppCard>
      <template #content>
        <div class="header-row">
          <span class="text-sm" v-if="tasks.length">{{ t('download.queue.total', { n: tasks.length }) }}</span>
          <AppButton
            icon="pi pi-refresh"
            @click="fetchTasks()"
            size="s"
            type="ghost"
          />
        </div>
        <AppTable v-if="tasks.length" :value="tasks" size="small">
          <Column field="task_id" :header="t('download.queue.col_task_id')" />
          <Column field="task_type" :header="t('download.queue.col_type')" />
          <Column :header="t('download.queue.col_status')">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="data.status === 'running' ? 'info' : data.status === 'completed' ? 'success' : 'warn'" />
            </template>
          </Column>
          <Column field="total_items" :header="t('download.queue.col_items')" />
          <Column :header="t('download.queue.col_created')">
            <template #body="{ data }">{{ new Date(data.created_at).toLocaleString('zh-CN') }}</template>
          </Column>
          <Column :header="t('download.queue.col_action')">
            <template #body="{ data }">
              <AppButton
                v-if="data.status === 'running'"
                icon="pi pi-times"
                text
                size="s"
                type="danger"
                :title="t('task.stop')"
                @click="cancelTask(data.task_id)"
              />
            </template>
          </Column>
        </AppTable>
        <p v-else-if="!loading" class="empty">{{ t('download.queue.empty') }}</p>
      </template>
    </AppCard>
  </PageContainer>
</template>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-12); }
.text-sm { font-size: var(--font-size-13); color: var(--text-secondary); }
.empty { padding: var(--space-32) 0; text-align: center; color: var(--text-secondary); }
</style>
