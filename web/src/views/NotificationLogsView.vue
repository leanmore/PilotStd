<script setup lang="ts">
defineOptions({ name: 'NotificationLogsView' })
// 文案全部走 i18n（notification.logs.* / notification.channel.*），不硬编码中文
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Select from 'primevue/select'
import AppCalendar from '@/components/AppCalendar.vue'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import { getNotificationLogs, deleteNotificationLogs, type NotificationLog } from '@/api/notification'
import { getItem, setItem } from '@/lib/storage'

const route = useRoute()
const { t, te } = useI18n()

const logs = ref<NotificationLog[]>([])
const total = ref(0)
const page = ref(Number(getItem('notiflog_page')) || 1)
const pageSize = 20
const loading = ref(false)
const errMsg = ref('')
const tableHeight = ref(Number(getItem('notiflog_height')) || 400)

// 拖拽调整高度
let startY = 0
let startHeight = 0

function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  startY = e.clientY
  startHeight = tableHeight.value
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  const delta = e.clientY - startY
  tableHeight.value = Math.max(200, Math.min(800, startHeight + delta))
}

function onResizeEnd() {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  setItem('notiflog_height', String(tableHeight.value))
}

// 筛选
// 说明：本页是**诊断工具**（排查"通知有没有发出去"），不是阅读渠道。
// 故不提供"已读/未读"筛选与显示——渠道（Telegram 等）不提供已读回传，
// 「已读」只能表示"用户在 Web 界面点过标记"，与"通知是否送达/是否看过"无关。
const filterChannel = ref<string | null>(null)
const filterStatus = ref<string | null>(null)
const filterStartDate = ref<Date | null>(null)
const filterEndDate = ref<Date | null>(null)

function loadNotifFilters() {
  try {
    const raw = getItem('notiflog_filters')
    if (!raw) return
    const f = JSON.parse(raw)
    filterChannel.value = f.ch ?? null
    filterStatus.value = f.st ?? null
    filterStartDate.value = f.sd ? new Date(f.sd) : null
    filterEndDate.value = f.ed ? new Date(f.ed) : null
  } catch { /* ignore */ }
}

function saveNotifFilters() {
  setItem('notiflog_filters', JSON.stringify({
    ch: filterChannel.value, st: filterStatus.value,
    sd: filterStartDate.value?.toISOString() ?? null,
    ed: filterEndDate.value?.toISOString() ?? null,
  }))
}

watch([filterChannel, filterStatus, filterStartDate, filterEndDate], saveNotifFilters, { deep: true })
const highlightId = ref<number | null>(null)

// 详情弹窗
const detailVisible = ref(false)
const detailItem = ref<NotificationLog | null>(null)

// 清理日志弹窗
const cleanupVisible = ref(false)
const cleanupDays = ref(30)
const cleanupLoading = ref(false)
const cleanupResult = ref('')

async function doCleanup() {
  cleanupLoading.value = true
  cleanupResult.value = ''
  try {
    const r = await deleteNotificationLogs(cleanupDays.value)
    cleanupResult.value = t('notification.logs.cleanup_result', { n: r.deleted })
    cleanupVisible.value = false
    loadLogs()
  } catch (e: any) {
    cleanupResult.value = e.response?.data?.error || t('notification.logs.cleanup_failed')
  } finally {
    cleanupLoading.value = false
  }
}

const channelOptions = computed(() => [
  { label: t('notification.logs.status.all'), value: null },
  { label: t('notification.channel.wechat'), value: 'wechat' },
  { label: t('notification.channel.telegram'), value: 'telegram' },
  { label: t('notification.channel.feishu'), value: 'feishu' },
])
const statusOptions = computed(() => [
  { label: t('notification.logs.status.all'), value: null },
  { label: t('notification.logs.status.success'), value: 'success' },
  { label: t('notification.logs.status.failed'), value: 'failed' },
])

// 渠道显示名：仅已配置 i18n 的渠道做映射，未知渠道原样回显（保持既有行为）
const CHANNEL_KEYS: Record<string, string> = {
  wechat: 'notification.channel.wechat',
  telegram: 'notification.channel.telegram',
  feishu: 'notification.channel.feishu',
}

function channelLabel(v: string): string {
  const k = CHANNEL_KEYS[v]
  return k ? t(k) : v
}

function statusSeverity(s: string): 'success' | 'danger' | 'info' {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
}

function statusLabel(s: string): string {
  return s === 'success' ? t('notification.logs.status.success') : t('notification.logs.status.failed')
}

// 事件类型 → i18n key（notification.event.<type>，与配置页共用同一套文案）；未知类型原样回显
function eventLabel(v: string): string {
  const key = `notification.event.${v}`
  return te(key) ? t(key) : v
}

async function loadLogs() {
  loading.value = true
  errMsg.value = ''
  try {
    const formatDate = (d: Date | null) => d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` : undefined
    const r = await getNotificationLogs({
      page: page.value,
      page_size: pageSize,
      channel: filterChannel.value || undefined,
      status: filterStatus.value || undefined,
      start_date: formatDate(filterStartDate.value),
      end_date: formatDate(filterEndDate.value),
    }, '/notification-logs')
    logs.value = r.items
    total.value = r.total
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || t('notification.logs.load_failed')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  loadLogs()
}

function onReset() {
  filterChannel.value = null
  filterStatus.value = null
  filterStartDate.value = null
  filterEndDate.value = null
  page.value = 1
  loadLogs()
}

function onPageChange(p: number) {
  page.value = p
  setItem('notiflog_page', String(p))
  loadLogs()
}

function showDetail(item: NotificationLog) {
  detailItem.value = item
  detailVisible.value = true
}

// 临时高亮行样式
function rowClass(item: NotificationLog) {
  return item.id === highlightId.value ? 'highlight-row' : ''
}

// 监听 URL highlight 参数
watch(
  () => route.query.highlight,
  (val) => {
    if (val) {
      highlightId.value = Number(val)
      setTimeout(() => {
        const el = document.querySelector('.highlight-row') as HTMLElement | null
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 300)
    }
  },
)

const totalPages = () => Math.max(1, Math.ceil(total.value / pageSize))
const pages = () => {
  const tp = totalPages()
  const p = page.value
  const range: number[] = []
  let start = Math.max(1, p - 2)
  let end = Math.min(tp, p + 2)
  if (end - start < 4) {
    if (start === 1) end = Math.min(tp, start + 4)
    else start = Math.max(1, end - 4)
  }
  for (let i = start; i <= end; i++) range.push(i)
  return range
}

onMounted(() => { loadNotifFilters(); loadLogs() })
// ✅ #45: 防御性清理拖拽监听器
onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">{{ t('notification.logs.title') }}</h2>

    <!-- 筛选区 -->
    <div class="card section">
      <div class="card-header">{{ t('notification.logs.filter_title') }}</div>
      <div class="filter-row">
        <div class="filter-item">
          <label>{{ t('notification.logs.field.channel') }}</label>
          <Select v-model="filterChannel" :options="channelOptions" optionLabel="label" optionValue="value" />
        </div>
        <div class="filter-item">
          <label>{{ t('notification.logs.field.status') }}</label>
          <Select v-model="filterStatus" :options="statusOptions" optionLabel="label" optionValue="value" />
        </div>
        <div class="filter-item">
          <label>{{ t('notification.logs.start_date') }}</label>
          <AppCalendar v-model="filterStartDate" dateFormat="yy-mm-dd" showIcon />
        </div>
        <div class="filter-item">
          <label>{{ t('notification.logs.end_date') }}</label>
          <AppCalendar v-model="filterEndDate" dateFormat="yy-mm-dd" showIcon />
        </div>
        <div class="filter-actions">
          <Button icon="pi pi-search" :label="t('notification.logs.search')" size="small" @click="onSearch" />
          <Button icon="pi pi-refresh" :label="t('notification.logs.reset')" size="small" severity="secondary" @click="onReset" />
        </div>
      </div>
    </div>

    <!-- 日志列表 -->
    <div class="card section">
      <div class="card-header">
        <span>{{ t('notification.logs.list_title') }}</span>
        <div style="display:flex;gap:8px">
          <Button icon="pi pi-trash" :label="t('notification.logs.cleanup')" size="small" severity="danger" outlined @click="cleanupVisible = true" />
          <Button icon="pi pi-refresh" size="small" severity="secondary" :loading="loading" @click="loadLogs" />
        </div>
      </div>
      <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>

      <div class="table-meta">
        <span>{{ t('notification.logs.total', { n: total }) }}</span>
        <span v-if="total > 0">{{ t('notification.logs.page', { page, pages: totalPages() }) }}</span>
      </div>

      <div class="resizable-table" :style="{ height: tableHeight + 'px' }">
        <div class="table-scroll">
          <table class="log-table" v-if="logs.length">
            <thead>
              <tr>
                <th>{{ t('notification.logs.field.time') }}</th>
                <th>{{ t('notification.logs.field.channel') }}</th>
                <th>{{ t('notification.logs.field.event') }}</th>
                <th>{{ t('notification.logs.field.status') }}</th>
                <th>{{ t('notification.logs.field.title') }}</th>
                <th>{{ t('notification.logs.field.action') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in logs" :key="l.id" :class="rowClass(l)">
                <td>{{ l.sent_at?.replace('T', ' ').substring(0, 16) }}</td>
                <td>{{ channelLabel(l.channel) }}</td>
                <td>{{ eventLabel(l.event_type) }}</td>
                <td><Tag :severity="statusSeverity(l.status)" :value="statusLabel(l.status)" /></td>
                <td class="title-cell">{{ l.title }}</td>
                <td><Button :label="t('notification.logs.view')" size="small" severity="secondary" text @click="showDetail(l)" /></td>
              </tr>
            </tbody>
          </table>
          <p v-else-if="!loading" class="empty">{{ t('notification.logs.empty') }}</p>
        </div>
        <div class="resize-handle" @mousedown="onResizeStart" :title="t('notification.logs.resize_title')" />
      </div>

      <div class="pagination" v-if="totalPages() > 1">
        <Button icon="pi pi-angle-left" size="small" severity="secondary" text :disabled="page <= 1" @click="onPageChange(page - 1)" />
        <Button v-for="p in pages()" :key="p" :label="String(p)" size="small" :severity="p === page ? 'primary' : 'secondary'" text @click="onPageChange(p)" />
        <Button icon="pi pi-angle-right" size="small" severity="secondary" text :disabled="page >= totalPages()" @click="onPageChange(page + 1)" />
      </div>
    </div>

    <Dialog v-model:visible="detailVisible" :header="t('notification.logs.detail_title')" :style="{ width: '500px' }" modal>
      <div v-if="detailItem" class="detail">
        <div class="detail-row"><span>{{ t('notification.logs.field.time') }}</span><span>{{ detailItem.sent_at }}</span></div>
        <div class="detail-row"><span>{{ t('notification.logs.field.channel') }}</span><span>{{ channelLabel(detailItem.channel) }}</span></div>
        <div class="detail-row"><span>{{ t('notification.logs.field.event') }}</span><span>{{ eventLabel(detailItem.event_type) }}</span></div>
        <div class="detail-row"><span>{{ t('notification.logs.field.status') }}</span><Tag :severity="statusSeverity(detailItem.status)" :value="statusLabel(detailItem.status)" /></div>
        <div class="detail-row"><span>{{ t('notification.logs.field.title') }}</span><span>{{ detailItem.title }}</span></div>
        <div class="detail-body"><span>{{ t('notification.logs.field.body') }}</span><pre>{{ detailItem.body }}</pre></div>
        <div v-if="detailItem.error_msg" class="detail-row"><span>{{ t('notification.logs.field.error') }}</span><span class="err">{{ detailItem.error_msg }}</span></div>
      </div>
    </Dialog>

    <!-- 清理日志确认弹窗 -->
    <Dialog v-model:visible="cleanupVisible" :header="t('notification.logs.cleanup_title')" :style="{ width: '420px' }" modal>
      <div>
        <p style="margin:0 0 12px;color:var(--text-dim)">{{ t('notification.logs.cleanup_hint') }}</p>
        <div style="display:flex;align-items:center;gap:8px">
          <label>{{ t('notification.logs.cleanup_keep') }}</label>
          <input
            v-model.number="cleanupDays"
            type="number"
            min="1"
            max="365"
            style="width:80px;padding:8px;border:1px solid var(--border);border-radius:var(--radius-sm);text-align:center"
          />
          <label>{{ t('notification.logs.cleanup_days') }}</label>
        </div>
        <p v-if="cleanupResult" style="margin-top:12px;font-size:12px;color:var(--primary)">{{ cleanupResult }}</p>
      </div>
      <template #footer>
        <Button :label="t('common.cancel')" size="small" severity="secondary" text @click="cleanupVisible = false" />
        <Button :label="t('notification.logs.cleanup_confirm')" size="small" severity="danger" :loading="cleanupLoading" @click="doCleanup" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.section { margin-bottom: 16px; }

/* 筛选区 */
.filter-row { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.filter-item { display: flex; flex-direction: column; gap: 6px; min-width: 140px; flex: 1; }
.filter-item label { font-size: 12px; font-weight: 500; color: var(--text-secondary); }
.filter-actions { display: flex; gap: 8px; align-items: flex-end; padding-bottom: 1px; }

/* 可调整高度的表格容器 */
.resizable-table {
  position: relative;
  height: 400px;
  min-height: 200px;
  max-height: 800px;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.table-scroll {
  height: calc(100% - 8px);
  overflow-y: auto;
  overflow-x: auto;
}
.log-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 700px; }
.log-table th { position: sticky; top: 0; background: var(--surface-raised); z-index: 1; }
.log-table th, .log-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.log-table th { font-weight: 600; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
.title-cell { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { color: var(--text-dim); font-size: 14px; padding: 32px 0; text-align: center; }

/* 拖拽手柄 */
.resize-handle {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 8px;
  cursor: ns-resize;
  background: transparent;
  z-index: 10;
  transition: background 0.2s;
}
.resize-handle:hover {
  background: rgba(99, 102, 241, 0.2);
}
.resize-handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 3px;
  background: var(--border);
  border-radius: 2px;
}
.resize-handle:hover::after {
  background: var(--primary);
  height: 4px;
}

/* 分页 */
.pagination { display: flex; justify-content: center; align-items: center; gap: 4px; margin-top: 16px; }

/* 详情弹窗 */
.detail { display: flex; flex-direction: column; gap: 12px; }
.detail-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.detail-row span:first-child { color: var(--text-dim); }
.detail-body { font-size: 13px; }
.detail-body span { color: var(--text-dim); }
.detail-body pre { margin: 4px 0 0; padding: 10px; background: var(--bg); border-radius: var(--radius-sm); font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.err { color: var(--danger) !important; }
</style>
