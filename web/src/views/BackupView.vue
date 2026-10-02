<script setup lang="ts">
defineOptions({ name: 'BackupView' })
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Divider from 'primevue/divider'
import { getBackupList, createBackup as createBackupApi } from '@/api/backup'
import type { RouteTag } from '@/types/route-tag'
import { useAppStore } from '@/stores/app'

interface Backup {
  id: string; name: string; size: number; size_mb: number; created_at: string
}

const backups = ref<Backup[]>([])
const loading = ref(false)
const creating = ref(false)
const { t } = useI18n()
const store = useAppStore()

// 创建备份要求 admin：后端 `POST /api/backup/create` 已加 `@require_role("admin")`
// （备份含全量数据库内容）。前端同步门控，避免非 admin 看到可点但必然 403 的按钮。
const isAdmin = computed(() => store.role === 'admin')

const lastBackup = ref<string | null>(null)

const formatTime = (iso: string) => new Date(iso).toLocaleString('zh-CN')

const fetchBackups = async (routeTag?: RouteTag) => {
  loading.value = true
  try {
    const resp = await getBackupList(routeTag ? { routeTag } : undefined)
    backups.value = resp.data.items || []
    if (backups.value.length > 0) lastBackup.value = backups.value[0].created_at
  } catch { /* ignore */ }
  finally { loading.value = false }
}

const createBackup = async () => {
  creating.value = true
  try {
    const resp = await createBackupApi()
    if (resp.data.ok) await fetchBackups('/backup')
  } catch { /* ignore */ }
  finally { creating.value = false }
}

onMounted(() => fetchBackups('/backup'))
</script>

<template>
  <div class="page">
    <h2 class="page-title">{{ t('backup.title') }}</h2>
    <Card>
      <template #content>
        <div class="flex gap-3 align-items-center">
          <Button
            v-if="isAdmin"
            :label="t('backup.create')"
            icon="pi pi-plus"
            @click="createBackup"
            :loading="creating"
          />
          <span v-if="lastBackup" class="text-sm">{{ t('backup.last_backup', { time: formatTime(lastBackup) }) }}</span>
        </div>
        <Divider />
        <DataTable :value="backups" :loading="loading" striped-rows size="small">
          <Column field="name" :header="t('backup.col_name')" />
          <Column field="size_mb" :header="t('backup.col_size')" />
          <Column :header="t('backup.col_created')">
            <template #body="{ data }">{{ formatTime(data.created_at) }}</template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 900px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.flex { display: flex; }
.gap-3 { gap: 12px; }
.align-items-center { align-items: center; }
.text-sm { font-size: 13px; color: var(--text-color-secondary); }
</style>
