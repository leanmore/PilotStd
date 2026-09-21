<script setup lang="ts">
defineOptions({ name: 'AnnounceDetail' })
import { ref, onMounted, onBeforeUnmount, computed, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import DOMPurify from 'dompurify'
import {
  getAnnounceDetailLite,
  getAnnounceRecords,
  triggerParse,
  getParseStatus,
  updateRecord,
  batchApprove,
} from '@/api/announce'
import type { Announcement, AnnouncementRecord } from '@/types/api'
import type { RecordFetcher } from '@/composables/useIncrementalScroll'
import { useDetailCache } from '@/composables/useDetailCache'
import { useFavorite } from '@/composables/useFavorite'
import { useIncrementalScroll } from '@/composables/useIncrementalScroll'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import AppCalendar from '@/components/AppCalendar.vue'
import TableLoadFooter from '@/components/TableLoadFooter.vue'
import FavoriteStatusTag from '@/components/FavoriteStatusTag.vue'

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

// ═══ #40 增量加载（方案 C 哨兵 + Phase 2 分页化开关）═══
const usePaginated = import.meta.env.VITE_USE_PAGINATED_RECORDS_API === 'true'
const sentinel = ref<HTMLElement | null>(null)
const recordsSource: Ref<AnnouncementRecord[]> | RecordFetcher = usePaginated ? (page: number, pageSize: number) => getAnnounceRecords(announceNo, page, pageSize) : records
const {
  displayRecords,
  isLoadingMore,
  showLoadAllButton,
  loadAllRemaining,
  totalCount,
  reload: reloadRecords,
} = useIncrementalScroll(recordsSource, sentinel)

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
  const raw = DOMPurify.sanitize(announcement.value?.content || '')
  return raw
})

async function loadDetail() {
  // 1. 优先读 sessionStorage 缓存
  const cached = getCache()
  if (cached) {
    announcement.value = cached.announcement
    parseStatus.value = cached.parse_status || 'pending'
    // 分页模式：records 走分页接口，缓存不提供记录数据
    if (!usePaginated) records.value = cached.records
    loading.value = false
    loadFavStatuses()
    return
  }

  // 2. 缓存未命中，正常请求
  loading.value = true
  try {
    const res = await getAnnounceDetailLite(announceNo, source, '/announce')
    announcement.value = res.announcement
    parseStatus.value = res.parse_status || 'pending'
    // 分页模式：仅取公告头与解析状态，记录数据由分页接口按页提供
    if (!usePaginated) records.value = res.records || []
    setCache({
      announcement: res.announcement,
      records: usePaginated ? [] : res.records,
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
  // ✅ #45: 防御性清理已有定时器
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  parsing.value = true
  parseStatus.value = 'parsing'
  try {
    await triggerParse(announceNo)
    let retries = 0
    const maxRetries = 30
    const interval = 2000
    pollTimer = setInterval(async () => {
      retries++
      try {
        const statusRes = await getParseStatus(announceNo)
        if (statusRes.status === 'completed') {
          clearInterval(pollTimer!)
          pollTimer = null
          parseStatus.value = 'completed'
          parsing.value = false
          clearDetailCache()
          await loadDetail()
          // 分页模式：条数取 parse-status 的 record_count；降级模式取本地 records
          const count = usePaginated ? (statusRes.record_count ?? 0) : records.value.length
          toast.add({ severity: 'success', summary: '解析完成', detail: `共 ${count} 条标准`, life: 3000 })
        } else if (statusRes.status === 'failed') {
          clearInterval(pollTimer!)
          pollTimer = null
          parseStatus.value = 'failed'
          parsing.value = false
          toast.add({ severity: 'error', summary: '解析失败', detail: '请检查附件格式', life: 3000 })
        } else if (retries >= maxRetries) {
          clearInterval(pollTimer!)
          pollTimer = null
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
    // 分页模式：重新拉第一页刷新列表；降级模式：重载全量
    if (usePaginated) {
      await reloadRecords()
    } else {
      await loadDetail()
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (Array.isArray(detail?.errors)) {
      toast.add({ severity: 'error', summary: '确认失败', detail: detail.errors.join('；'), life: 5000 })
    } else {
      toast.add({ severity: 'error', summary: '确认失败', detail: '请重试', life: 3000 })
    }
  }
}

// ── Phase 4a: 收藏（收藏状态与下载状态分开维护，判定见 @/utils/downloadStatus）──
// 分页模式下收藏状态基于已加载的 displayRecords（首屏 50 条）

const { favMap, favStatusMap, isFavLoading, toggleFavorite, loadFavStatuses } = useFavorite(
  usePaginated ? displayRecords : records,
)

// ✅ #45: 组件级 pollTimer，确保 onBeforeUnmount 可访问
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(loadDetail)

// ✅ #45: 组件卸载时清理轮询定时器
onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
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
            <span class="flex-1 text-center truncate px-2 text-xl font-semibold" style="color:var(--text-heading)">{{ announcement?.announce_no }}</span>
            <Tag :value="parseStatusLabel" :severity="parseStatusSeverity" />
            <Button
              icon="pi pi-undo"
              aria-label="返回列表"
              class="p-button-text p-button-rounded ml-3"
              @click="$router.back()"
            />
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
              <div class="official-doc mt-1 p-3 border-round">
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
            :value="displayRecords"
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
            <Column header="收藏" style="width: 9rem">
              <template #body="{ data }">
                <div class="fav-cell">
                  <Button
                    :icon="favMap[data.id] ? 'pi pi-star-fill' : 'pi pi-star'"
                    :loading="isFavLoading(data.id)"
                    rounded text size="small"
                    :severity="favMap[data.id] ? 'warn' : 'secondary'"
                    @click.stop="toggleFavorite(data)"
                  />
                  <!-- 收藏对象存在才渲染下载状态标签（不存在则不渲染，星标保持空心） -->
                  <FavoriteStatusTag :status="favStatusMap[data.id]" />
                </div>
              </template>
            </Column>
          </DataTable>

          <TableLoadFooter
            :displayed="displayRecords.length"
            :total="usePaginated ? totalCount : records.length"
            :is-loading="isLoadingMore"
            :show-load-all-button="showLoadAllButton"
            @load-all="loadAllRemaining"
          />
          <!-- 滚动加载哨兵：进入视口前 100px 触发下一批加载（方案 C，不占视觉空间） -->
          <div ref="sentinel" class="scroll-sentinel" style="height: 1px; opacity: 0;" aria-hidden="true" />
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
  background: var(--bg);
  min-height: 100vh;
}

.p-button-text.p-button-rounded:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* fix(a11y): 标题/公告号强制 --text-heading，阻断 Aura 亮色 token 继承（深色主题 1.8:1→≥8:1）。标题居中 — :deep() 穿透 Card，提高特异性对抗 Aura 的 .p-card-content p */
:deep(.p-card-content) .announce-title {
  font-size: 22px;
  font-weight: bold;
  text-align: center;
  line-height: 1.8;
  margin: 0.5rem 0; color: var(--text-heading);
}

.official-doc {
  max-width: 800px;
  margin: 0 auto;
  background: var(--surface);
}

/* 正文通用容器 — 两端对齐 + 舒适行距，作为无特定 class 段落的回退 */
.doc-content {
  color: var(--text);
  text-align: justify;
  line-height: 1.8;
}

/* 通用段落缩进 — 作用于正文区所有段落，优先级低于特定 class */
.doc-content :where(p, section > p, div > p) {
  text-indent: 2em;
  margin: 0.5em 0;
}

/* v-html 注入内容的标题居中 — 仅作用于 official-doc 容器内 */
:deep(.official-doc .announce-heading) {
  text-align: center;
  font-weight: 700;
  text-indent: 0;
  margin-bottom: 0.5em;
}

/* 正文段落 — 两端对齐、首行缩进 */
.doc-content :deep(.announce-body) {
  font-size: 16px;
  color: var(--text);
  text-indent: 2em;
  text-align: justify;
  line-height: 1.8;
  margin: 0.25em 0;
}

/* 落款机关 — 右对齐、无缩进 */
.doc-content :deep(.announce-signature) {
  font-size: 16px;
  color: var(--text);
  text-align: right;
  text-indent: 0;
  line-height: 1.8;
  margin: 0.25em 0;
}

/* 落款日期 — 右对齐、无缩进 */
.doc-content :deep(.announce-date) {
  font-size: 16px;
  color: var(--text);
  text-align: right;
  text-indent: 0;
  line-height: 1.8;
  margin: 0.25em 0;
}

.doc-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.doc-content :deep(td),
.doc-content :deep(th) {
  border: 1px solid var(--border);
  padding: 0.25rem 0.5rem;
}

.attachment-area {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 收藏单元格：星标 + 下载状态标签（标签仅在收藏对象存在时渲染） */
.fav-cell {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
</style>
