<script setup lang="ts">
defineOptions({ name: 'AnnounceDetail' })
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import DOMPurify from 'dompurify'
import {
  getAnnouncementDetail,
  triggerParse,
  getParseStatus,
  updateRecord,
  batchApprove,
  addFavorite,
  getFavoriteStatus,
  removeFavorite,
} from '@/api/announce'
import type { Announcement, AnnouncementRecord } from '@/types/api'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import AppCalendar from '@/components/AppCalendar.vue'

const route = useRoute()
const toast = useToast()
const source = route.params.source as string
const announceNo = route.params.announceNo as string

const loading = ref(true)
const parsing = ref(false)
const announcement = ref<Announcement | null>(null)
const records = ref<AnnouncementRecord[]>([])
const selectedRecords = ref<AnnouncementRecord[]>([])
const parseStatus = ref<'pending' | 'parsing' | 'completed' | 'failed'>('pending')

const parseStatusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: '待解析', parsing: '解析中...', completed: '已解析', failed: '解析失败',
  }
  return map[parseStatus.value] || '未知'
})

const parseStatusSeverity = computed(() => {
  const map: Record<string, 'secondary' | 'info' | 'success' | 'danger'> = {
    pending: 'secondary', parsing: 'info', completed: 'success', failed: 'danger',
  }
  return map[parseStatus.value] || 'secondary'
})

const parseButtonLabel = computed(() => {
  if (parseStatus.value === 'completed') return '重新解析'
  if (parsing.value) return '解析中'
  if (!announcement.value?.attachment_url) return '无附件'
  return '开始解析'
})

const parseButtonDisabled = computed(() => {
  if (parsing.value) return true
  if (!announcement.value?.attachment_url) return true
  return false
})

const sanitizedContent = computed(() => {
  return DOMPurify.sanitize(announcement.value?.content || '')
})

async function loadDetail() {
  loading.value = true
  try {
    const res = await getAnnouncementDetail(announceNo, source)
    announcement.value = res.announcement
    records.value = res.records || []
    parseStatus.value = res.parse_status || 'pending'
    loadFavStatuses()
  } catch {
    toast.add({ severity: 'error', summary: '加载失败', detail: '无法加载公告详情', life: 3000 })
  } finally {
    loading.value = false
  }
}

async function startParse() {
  if (!announcement.value?.attachment_url) {
    toast.add({ severity: 'warn', summary: '提示', detail: '该公告没有附件', life: 3000 })
    return
  }
  parsing.value = true
  parseStatus.value = 'parsing'
  try {
    await triggerParse(announceNo)
    let retries = 0
    const maxRetries = 30
    const interval = 2000
    const poll = setInterval(async () => {
      retries++
      try {
        const statusRes = await getParseStatus(announceNo)
        if (statusRes.status === 'completed') {
          clearInterval(poll)
          parseStatus.value = 'completed'
          parsing.value = false
          await loadDetail()
          toast.add({ severity: 'success', summary: '解析完成', detail: `共 ${records.value.length} 条标准`, life: 3000 })
        } else if (statusRes.status === 'failed') {
          clearInterval(poll)
          parseStatus.value = 'failed'
          parsing.value = false
          toast.add({ severity: 'error', summary: '解析失败', detail: '请检查附件格式', life: 3000 })
        } else if (retries >= maxRetries) {
          clearInterval(poll)
          parsing.value = false
          toast.add({ severity: 'warn', summary: '超时', detail: '解析超时，请稍后刷新查看', life: 3000 })
        }
      } catch { /* 轮询出错继续 */ }
    }, interval)
  } catch {
    parseStatus.value = 'failed'
    parsing.value = false
    toast.add({ severity: 'error', summary: '启动失败', detail: '无法触发解析任务', life: 3000 })
  }
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    draft: '草稿', pending_review: '待校对', approved: '已确认', rejected: '已驳回',
  }
  return map[status] || status
}

function statusSeverity(status: string) {
  const map: Record<string, 'secondary' | 'warn' | 'success' | 'danger'> = {
    draft: 'secondary', pending_review: 'warn', approved: 'success', rejected: 'danger',
  }
  return map[status] || 'secondary'
}

async function onCellEditComplete(event: any) {
  const { data, newValue, field } = event
  const oldValue = data[field]
  if (data.status === 'approved') {
    data[field] = oldValue
    toast.add({ severity: 'warn', summary: '提示', detail: '已确认的记录不可编辑', life: 3000 })
    return
  }
  data[field] = newValue
  try {
    await updateRecord(data.id, { [field]: newValue })
    if (data.status === 'draft') {
      data.status = 'pending_review'
    }
    toast.add({ severity: 'success', summary: '保存成功', life: 2000 })
  } catch {
    data[field] = oldValue
    toast.add({ severity: 'error', summary: '保存失败', detail: '请重试', life: 3000 })
  }
}

async function handleBatchApprove() {
  const ids = selectedRecords.value.map(r => r.id)
  if (ids.length === 0) return
  try {
    const res = await batchApprove(ids)
    toast.add({ severity: 'success', summary: '确认成功', detail: `已确认 ${res.approved_count} 条标准`, life: 3000 })
    selectedRecords.value = []
    await loadDetail()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (Array.isArray(detail?.errors)) {
      toast.add({ severity: 'error', summary: '确认失败', detail: detail.errors.join('；'), life: 5000 })
    } else {
      toast.add({ severity: 'error', summary: '确认失败', detail: '请重试', life: 3000 })
    }
  }
}

// ── Phase 4a: 收藏 ──────────────────────────────────────

const favStatusMap = ref<Record<number, string>>({})
const favLoadingMap = ref<Record<number, boolean>>({})
const favPollTimers = ref<Record<number, ReturnType<typeof setInterval>>>({})

function favLabel(status: string) {
  const map: Record<string, string> = { pending: '待处理', downloading: '下载中', archiving: '归档中' }
  return map[status] || status
}

function favIcon(recordId: number) {
  const s = favStatusMap.value[recordId]
  if (s === 'done') return 'pi pi-star-fill'
  if (s === 'downloading' || s === 'archiving') return 'pi pi-spin pi-spinner'
  if (s === 'failed') return 'pi pi-exclamation-triangle'
  return 'pi pi-star'
}

function isFavLoading(recordId: number) {
  return !!favLoadingMap.value[recordId]
}

async function toggleFavorite(record: AnnouncementRecord) {
  const current = favStatusMap.value[record.id]
  if (current === 'done') {
    try {
      await removeFavorite(record.id)
      delete favStatusMap.value[record.id]
      stopFavPoll(record.id)
      toast.add({ severity: 'success', summary: '已取消收藏', life: 2000 })
    } catch {
      toast.add({ severity: 'error', summary: '取消失败', life: 3000 })
    }
    return
  }
  if (current && current !== 'failed') return

  favLoadingMap.value[record.id] = true
  try {
    const res = await addFavorite(record.id)
    favStatusMap.value[record.id] = res.status
    if (res.status === 'pending') startFavPoll(record.id)
  } catch {
    toast.add({ severity: 'error', summary: '收藏失败', life: 3000 })
  } finally {
    favLoadingMap.value[record.id] = false
  }
}

function startFavPoll(recordId: number) {
  stopFavPoll(recordId)
  let attempts = 0
  favPollTimers.value[recordId] = setInterval(async () => {
    attempts++
    try {
      const res = await getFavoriteStatus(recordId)
      if (res.status === 'done' || res.status === 'failed') {
        stopFavPoll(recordId)
        favStatusMap.value[recordId] = res.status || 'failed'
        toast.add({
          severity: res.status === 'done' ? 'success' : 'error',
          summary: res.status === 'done' ? '归档完成' : '归档失败',
          detail: res.status === 'done' ? '已归档到标准库' : (res.error_message || '请重试'),
          life: 3000,
        })
        return
      }
      if (res.status) favStatusMap.value[recordId] = res.status
    } catch { /* continue */ }
    if (attempts >= 30) {
      stopFavPoll(recordId)
      favStatusMap.value[recordId] = 'failed'
      toast.add({ severity: 'warn', summary: '超时', detail: '归档处理超时', life: 5000 })
    }
  }, 2000)
}

function stopFavPoll(recordId: number) {
  if (favPollTimers.value[recordId]) {
    clearInterval(favPollTimers.value[recordId])
    delete favPollTimers.value[recordId]
  }
}

async function loadFavStatuses() {
  const results = await Promise.allSettled(
    records.value.map(r => getFavoriteStatus(r.id).catch(() => ({ status: null })))
  )
  results.forEach((res, i) => {
    if (res.status === 'fulfilled' && res.value.status) {
      favStatusMap.value[records.value[i].id] = res.value.status
    }
  })
}

onMounted(loadDetail)
onUnmounted(() => Object.keys(favPollTimers.value).forEach(id => stopFavPoll(Number(id))))
</script>

<template>
  <div class="announce-detail">
    <div v-if="loading" class="flex justify-content-center align-items-center" style="min-height: 400px">
      <ProgressSpinner />
    </div>

    <div v-else>
      <!-- 公告头 -->
      <Card class="mb-4">
        <template #title>
          <div class="flex justify-content-between align-items-center">
            <span class="text-xl font-semibold">{{ announcement?.announce_no }}</span>
            <Tag :value="parseStatusLabel" :severity="parseStatusSeverity" />
          </div>
        </template>
        <template #content>
          <div class="grid">
            <div class="col-12">
              <label class="text-sm text-color-secondary">标题</label>
              <p class="font-medium">{{ announcement?.title }}</p>
            </div>
            <div class="col-6">
              <label class="text-sm text-color-secondary">发布日期</label>
              <p>{{ announcement?.publish_date || '-' }}</p>
            </div>
            <div class="col-6">
              <label class="text-sm text-color-secondary">来源</label>
              <p>
                <a
                  v-if="announcement?.source_url"
                  :href="announcement.source_url"
                  target="_blank"
                  class="text-primary hover:underline"
                >{{ announcement.site_name || announcement.source_url }}</a>
                <span v-else>{{ announcement?.source_type || announcement?.site_name || '未知来源' }}</span>
              </p>
            </div>
            <div class="col-12">
              <label class="text-sm text-color-secondary">附件</label>
              <div class="attachment-area mt-1">
                <span v-if="announcement?.attachment_url" class="text-sm">
                  {{ announcement.attachment_url.split('/').pop() }}
                </span>
                <span v-else class="text-sm text-color-secondary">无附件</span>
                <Button
                  :label="parseButtonLabel"
                  icon="pi pi-refresh"
                  size="small"
                  :loading="parsing"
                  :disabled="parseButtonDisabled"
                  @click="startParse"
                />
                <Tag v-if="parseStatus === 'completed'" severity="success" value="已解析" />
              </div>
            </div>
            <!-- 公告正文 -->
            <div v-if="announcement?.content" class="col-12">
              <label class="text-sm text-color-secondary">公告正文</label>
              <div
                class="content-body mt-1 p-3 border-round surface-100"
                v-html="sanitizedContent"
              />
            </div>
          </div>
        </template>
      </Card>

      <!-- 标准清单表格 -->
      <Card>
        <template #title>
          <div class="flex justify-content-between align-items-center">
            <span>标准清单（{{ records.length }} 条）</span>
            <Button
              label="批量确认入库"
              icon="pi pi-check"
              severity="success"
              size="small"
              :disabled="selectedRecords.length === 0"
              @click="handleBatchApprove"
            />
          </div>
        </template>
        <template #content>
          <DataTable
            v-model:selection="selectedRecords"
            :value="records"
            editMode="cell"
            dataKey="id"
            stripedRows
            size="small"
            @cell-edit-complete="onCellEditComplete"
          >
            <Column selectionMode="multiple" headerStyle="width: 3rem" />
            <Column field="row_index" header="#" style="width: 4rem">
              <template #body="slotProps">
                {{ String(slotProps.data.row_index).padStart(2, '0') }}
              </template>
            </Column>
            <Column field="standard_number" header="标准号" style="min-width: 12rem">
              <template #editor="{ data, field }">
                <InputText v-model="data[field]" class="w-full" />
              </template>
              <template #body="{ data }">
                <span :class="{ 'text-red-500': !data.standard_number }">
                  {{ data.standard_number || '(待补全)' }}
                </span>
              </template>
            </Column>
            <Column field="std_name" header="标准名称" style="min-width: 18rem">
              <template #editor="{ data, field }">
                <InputText v-model="data[field]" class="w-full" />
              </template>
              <template #body="{ data }">
                <span :class="{ 'text-red-500': !data.std_name }">
                  {{ data.std_name || '(待补全)' }}
                </span>
              </template>
            </Column>
            <Column field="implement_date" header="实施日期" style="width: 10rem">
              <template #editor="{ data, field }">
                <AppCalendar v-model="data[field]" dateFormat="yy-mm-dd" showIcon />
              </template>
              <template #body="{ data }">
                {{ data.implement_date || '-' }}
              </template>
            </Column>
            <Column field="expiry_date" header="作废日期" style="width: 10rem">
              <template #editor="{ data, field }">
                <AppCalendar v-model="data[field]" dateFormat="yy-mm-dd" showIcon />
              </template>
              <template #body="{ data }">
                {{ data.expiry_date || '-' }}
              </template>
            </Column>
            <Column field="superseded_by" header="代替标准" style="min-width: 10rem">
              <template #editor="{ data, field }">
                <InputText v-model="data[field]" class="w-full" />
              </template>
              <template #body="{ data }">
                {{ data.superseded_by || '-' }}
              </template>
            </Column>
            <Column field="status" header="状态" style="width: 8rem">
              <template #body="{ data }">
                <Tag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" />
              </template>
            </Column>
            <Column field="confidence" header="置信度" style="width: 6rem">
              <template #body="{ data }">
                <span v-if="data.confidence > 0">{{ (data.confidence * 100).toFixed(0) }}%</span>
                <span v-else class="text-color-secondary">-</span>
              </template>
            </Column>
            <Column header="收藏" style="width: 6rem">
              <template #body="{ data }">
                <div class="flex align-items-center gap-1">
                  <Button
                    :icon="favIcon(data.id)"
                    :loading="isFavLoading(data.id)"
                    rounded text size="small"
                    :severity="favStatusMap[data.id] === 'done' ? 'warn' : 'secondary'"
                    @click.stop="toggleFavorite(data)"
                  />
                  <Tag v-if="favStatusMap[data.id] && favStatusMap[data.id] !== 'done' && favStatusMap[data.id] !== 'failed'"
                    :value="favLabel(favStatusMap[data.id])" severity="info" style="font-size:10px" />
                  <Tag v-else-if="favStatusMap[data.id] === 'failed'"
                    value="失败" severity="danger" style="font-size:10px" />
                </div>
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.announce-detail {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
}

.content-body {
  max-height: 400px;
  overflow-y: auto;
  font-size: 0.9rem;
  line-height: 1.6;
}

.content-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.content-body :deep(td),
.content-body :deep(th) {
  border: 1px solid var(--p-surface-300);
  padding: 0.25rem 0.5rem;
}

.attachment-area {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
