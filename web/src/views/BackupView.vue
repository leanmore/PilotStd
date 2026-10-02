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

// 备份页**整体**要求 admin：后端两个端点均已加 `@require_role("admin")`
//   - `POST /api/backup/create` 导出含全量数据库内容（用户表/密码哈希/审计日志/通知凭证）；
//   - `GET  /api/backup/list`   备份文件的存在性与时间戳本身即信息（可推断系统状态与备份频率）。
// 前端同步门控：非 admin 不请求列表（否则必然 403）、不渲染列表，只显示提示。
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

onMounted(() => { if (isAdmin.value) fetchBackups('/backup') })
</script>

<template>
  <div class="page">
    <h2 class="page-title">{{ t('backup.title') }}</h2>
    <Card v-if="!isAdmin">
      <template #content>
        <p class="text-sm">{{ t('backup.admin_only') }}</p>
      </template>
    </Card>
    <Card v-else>
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
