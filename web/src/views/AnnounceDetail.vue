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
} from '@/api/announce'
import type { Announcement, AnnouncementRecord } from '@/types/api'
import { useDetailCache } from '@/composables/useDetailCache'
import { useFavorite } from '@/composables/useFavorite'
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

const { get: getCache, set: setCache, clear: clearDetailCache } = useDetailCache(source, announceNo)

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
  if (parsing.value) return '解析中'
  if (parseStatus.value === 'completed') return '重新解析'
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
  // 1. 优先读 sessionStorage 缓存
  const cached = getCache()
  if (cached) {
    announcement.value = cached.announcement
    records.value = cached.records
    parseStatus.value = cached.parse_status || 'pending'
    loading.value = false
    loadFavStatuses()
    return
  }

  // 2. 缓存未命中，正常请求
  loading.value = true
  try {
    const res = await getAnnouncementDetail(announceNo, source)
    announcement.value = res.announcement
    records.value = res.records || []
    parseStatus.value = res.parse_status || 'pending'
    setCache({
      announcement: res.announcement,
      records: res.records,
      parse_status: res.parse_status,
    })
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
          clearDetailCache()
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
    clearDetailCache()
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

// ── Phase 4a: 收藏（委托给 useFavorite composable）──

const { favStatusMap, favLabel, favIcon, isFavLoading, toggleFavorite, loadFavStatuses, cleanup } = useFavorite(records)

onMounted(loadDetail)
onUnmounted(cleanup)
</script>

<template>
  <div class="announce-detail">
    <div v-if="loading" class="flex justify-content-center align-items-center" style="min-height: 400px">
      <ProgressSpinner />
    </div>

    <div v-else>
      <!-- 顶部导航：返回按钮 -->
      <div class="back-nav mb-4">
        <Button
          label="返回列表"
          icon="pi pi-arrow-left"
          severity="secondary"
          text
          size="small"
          class="back-btn"
          @click="$router.back()"
        />
      </div>

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
              <p class="announce-title">{{ announcement?.title }}</p>
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
                  v-if="announcement?.attachment_url"
                  :label="parseButtonLabel"
                  icon="pi pi-refresh"
                  size="small"
                  :loading="parsing"
                  :disabled="parseButtonDisabled"
                  @click="startParse"
                />
              </div>
            </div>
            <!-- 公告正文 -->
            <div v-if="announcement?.content" class="col-12">
              <label class="text-sm text-color-secondary">公告正文</label>
              <div class="official-doc mt-1 p-3 border-round surface-100">
                <div class="doc-content" v-html="sanitizedContent" />
              </div>
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
            <Column field="publish_date" header="发布日期" style="min-width: 10rem">
              <template #editor="{ data, field }">
                <AppCalendar v-model="data[field]" dateFormat="yy-mm-dd" showIcon />
              </template>
              <template #body="{ data }">
                {{ data.publish_date || '-' }}
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

    <!-- 悬浮返回按钮 -->
    <div class="floating-back-btn" @click="$router.back()" title="返回列表">
      <i class="pi pi-arrow-left"></i>
      <span>返回列表</span>
    </div>
  </div>
</template>

<style scoped>
.announce-detail {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
}

.back-nav {
  padding-left: 0;
}

.back-btn {
  color: var(--text-dim) !important;
  transition: color 0.2s;
}

.back-btn:hover {
  color: var(--p-primary-color) !important;
}

.announce-title {
  font-size: 22px;
  font-weight: bold;
  text-align: center;
  line-height: 1.8;
  margin: 0.5rem 0;
}

.official-doc {
  max-width: 800px;
  margin: 0 auto;
}

.doc-content {
  color: var(--text);
}

.doc-content :deep(p) {
  font-size: 16px;
  color: var(--text);
  text-indent: 2em;
  line-height: 1.8;
  margin: 0.25em 0;
}

.doc-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.doc-content :deep(td),
.doc-content :deep(th) {
  border: 1px solid var(--p-surface-300);
  padding: 0.25rem 0.5rem;
}

.attachment-area {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 悬浮返回按钮 */
.floating-back-btn {
  position: fixed;
  bottom: 40px;
  right: 40px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 50px;
  background-color: var(--primary);
  color: #ffffff;
  font-weight: 600;
  box-shadow: var(--shadow-md);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.floating-back-btn:hover {
  background-color: var(--primary-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.floating-back-btn i {
  font-size: 1.1em;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .floating-back-btn {
    bottom: 20px;
    right: 20px;
    padding: 10px 16px;
    font-size: 14px;
  }
}
</style>
