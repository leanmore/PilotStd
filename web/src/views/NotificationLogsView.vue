<script setup lang="ts">
defineOptions({ name: 'NotificationLogsView' })
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Calendar from 'primevue/calendar'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import { getNotificationLogs, deleteNotificationLogs, type NotificationLog } from '@/api/notification'
import { getItem, setItem } from '@/lib/storage'

const route = useRoute()
const { locale } = useI18n()

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
const filterChannel = ref<string | null>(null)
const filterStatus = ref<string | null>(null)
const filterStartDate = ref<Date | null>(null)
const filterEndDate = ref<Date | null>(null)
const filterIsRead = ref<boolean | null>(null)

function loadNotifFilters() {
  try {
    const raw = getItem('notiflog_filters')
    if (!raw) return
    const f = JSON.parse(raw)
    filterChannel.value = f.ch ?? null
    filterStatus.value = f.st ?? null
    filterStartDate.value = f.sd ? new Date(f.sd) : null
    filterEndDate.value = f.ed ? new Date(f.ed) : null
    filterIsRead.value = f.ir ?? null
  } catch { /* ignore */ }
}

function saveNotifFilters() {
  setItem('notiflog_filters', JSON.stringify({
    ch: filterChannel.value, st: filterStatus.value,
    sd: filterStartDate.value?.toISOString() ?? null,
    ed: filterEndDate.value?.toISOString() ?? null,
    ir: filterIsRead.value,
  }))
}

watch([filterChannel, filterStatus, filterStartDate, filterEndDate, filterIsRead], saveNotifFilters, { deep: true })
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
    cleanupResult.value = `已清理 ${r.deleted} 条记录`
    cleanupVisible.value = false
    loadLogs()
  } catch (e: any) {
    cleanupResult.value = e.response?.data?.error || '清理失败'
  } finally {
    cleanupLoading.value = false
  }
}

const channelOptions = [
  { label: '全部', value: null },
  { label: '企业微信', value: 'wechat' },
  { label: 'Telegram', value: 'telegram' },
  { label: '飞书', value: 'feishu' },
]
const statusOptions = [
  { label: '全部', value: null },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]
const readOptions = [
  { label: '全部', value: null },
  { label: '未读', value: false },
  { label: '已读', value: true },
]

function channelLabel(v: string): string {
  const m: Record<string, string> = { wechat: '企业微信', telegram: 'Telegram', feishu: '飞书' }
  return m[v] || v
}

function statusSeverity(s: string): 'success' | 'danger' | 'info' {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
}

function eventLabel(v: string): string {
  const m: Record<string, string> = {
    archive_complete: '归档完成', standard_status_changed: '状态变更',
    standard_expired: '标准废止', standard_first_registered: '首次登记',
    check_batch_complete: '批次完成', announcement_fetch_complete: '公告抓取', auto_backup: '自动备份',
    announcement_check_complete: '定时公告检查', batch_download_complete: '批量下载完成',
    auto_scan_failed: '扫描异常',
    validity_batch_report: '时效性检查', validity_round_summary: '周期总结',
    validity_standard_failed: '检查失败', validity_system_failed: '系统异常',
    test: '测试',
  }
  return m[v] || v
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
      is_read: filterIsRead.value !== null ? filterIsRead.value : undefined,
    })
    logs.value = r.items
    total.value = r.total
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '加载日志失败'
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
</script>

<template>
  <div class="page">
    <h2 class="page-title">通知日志</h2>

    <!-- 筛选区 -->
    <div class="card section">
      <div class="card-header">筛选条件</div>
      <div class="filter-row">
        <div class="filter-item">
          <label>渠道</label>
          <Select v-model="filterChannel" :options="channelOptions" optionLabel="label" optionValue="value" />
        </div>
        <div class="filter-item">
          <label>状态</label>
          <Select v-model="filterStatus" :options="statusOptions" optionLabel="label" optionValue="value" />
        </div>
        <div class="filter-item">
          <label>已读</label>
          <Select v-model="filterIsRead" :options="readOptions" optionLabel="label" optionValue="value" />
        </div>
        <div class="filter-item">
          <label>开始日期</label>
          <Calendar v-model="filterStartDate" :locale="locale" dateFormat="yy-mm-dd" showIcon />
        </div>
        <div class="filter-item">
          <label>结束日期</label>
          <Calendar v-model="filterEndDate" :locale="locale" dateFormat="yy-mm-dd" showIcon />
        </div>
        <div class="filter-actions">
          <Button icon="pi pi-search" label="查询" size="small" @click="onSearch" />
          <Button icon="pi pi-refresh" label="重置" size="small" severity="secondary" @click="onReset" />
        </div>
      </div>
    </div>

    <!-- 日志列表 -->
    <div class="card section">
      <div class="card-header">
        <span>日志列表</span>
        <div style="display:flex;gap:8px">
          <Button icon="pi pi-trash" label="清理日志" size="small" severity="danger" outlined @click="cleanupVisible = true" />
          <Button icon="pi pi-refresh" size="small" severity="secondary" :loading="loading" @click="loadLogs" />
        </div>
      </div>
      <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>

      <div class="table-meta">
        <span>共 {{ total }} 条记录</span>
        <span v-if="total > 0">第 {{ page }}/{{ totalPages() }} 页</span>
      </div>

      <div class="resizable-table" :style="{ height: tableHeight + 'px' }">
        <div class="table-scroll">
          <table class="log-table" v-if="logs.length">
            <thead>
              <tr>
                <th>时间</th>
                <th>渠道</th>
                <th>事件</th>
                <th>状态</th>
                <th>已读</th>
                <th>标题</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in logs" :key="l.id" :class="rowClass(l)">
                <td>{{ l.sent_at?.replace('T', ' ').substring(0, 16) }}</td>
                <td>{{ channelLabel(l.channel) }}</td>
                <td>{{ eventLabel(l.event_type) }}</td>
                <td><Tag :severity="statusSeverity(l.status)" :value="l.status === 'success' ? '成功' : '失败'" /></td>
                <td>
                  <Tag v-if="l.is_read" severity="info" value="已读" />
                  <Tag v-else severity="warn" value="未读" />
                  <Tag v-if="l.aggregated_count && l.aggregated_count > 1" severity="info" :value="'×' + l.aggregated_count" style="margin-left:4px" />
                </td>
                <td class="title-cell">
                  <a v-if="l.link" :href="l.link" class="notif-link">{{ l.title }}</a>
                  <span v-else>{{ l.title }}</span>
                </td>
                <td><Button label="查看" size="small" severity="secondary" text @click="showDetail(l)" /></td>
              </tr>
            </tbody>
          </table>
          <p v-else-if="!loading" class="empty">暂无通知记录</p>
        </div>
        <div class="resize-handle" @mousedown="onResizeStart" title="拖拽调整高度" />
      </div>

      <div class="pagination" v-if="totalPages() > 1">
        <Button icon="pi pi-angle-left" size="small" severity="secondary" text :disabled="page <= 1" @click="onPageChange(page - 1)" />
        <Button v-for="p in pages()" :key="p" :label="String(p)" size="small" :severity="p === page ? 'primary' : 'secondary'" text @click="onPageChange(p)" />
        <Button icon="pi pi-angle-right" size="small" severity="secondary" text :disabled="page >= totalPages()" @click="onPageChange(page + 1)" />
      </div>
    </div>

    <Dialog v-model:visible="detailVisible" header="通知详情" :style="{ width: '500px' }" modal>
      <div v-if="detailItem" class="detail">
        <div class="detail-row"><span>时间</span><span>{{ detailItem.sent_at }}</span></div>
        <div class="detail-row"><span>渠道</span><span>{{ channelLabel(detailItem.channel) }}</span></div>
        <div class="detail-row"><span>事件</span><span>{{ eventLabel(detailItem.event_type) }}</span></div>
        <div class="detail-row"><span>状态</span><Tag :severity="statusSeverity(detailItem.status)" :value="detailItem.status === 'success' ? '成功' : '失败'" /></div>
        <div class="detail-row"><span>标题</span><span>{{ detailItem.title }}</span></div>
        <div class="detail-body"><span>内容</span><pre>{{ detailItem.body }}</pre></div>
        <div v-if="detailItem.error_msg" class="detail-row"><span>错误</span><span class="err">{{ detailItem.error_msg }}</span></div>
      </div>
    </Dialog>

    <!-- 清理日志确认弹窗 -->
    <Dialog v-model:visible="cleanupVisible" header="清理通知日志" :style="{ width: '420px' }" modal>
      <div>
        <p style="margin:0 0 12px;color:var(--text-dim)">删除指定天数之前的通知日志记录：</p>
        <div style="display:flex;align-items:center;gap:8px">
          <label>保留</label>
          <input
            v-model.number="cleanupDays"
            type="number"
            min="1"
            max="365"
            style="width:80px;padding:8px;border:1px solid var(--border);border-radius:var(--radius-sm);text-align:center"
          />
          <label>天</label>
        </div>
        <p v-if="cleanupResult" style="margin-top:12px;font-size:12px;color:var(--primary)">{{ cleanupResult }}</p>
      </div>
      <template #footer>
        <Button label="取消" size="small" severity="secondary" text @click="cleanupVisible = false" />
        <Button label="确认清理" size="small" severity="danger" :loading="cleanupLoading" @click="doCleanup" />
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
.filter-item label { font-size: 12px; font-weight: 500; color: var(--text-dim); }
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
.log-table th { font-weight: 600; color: var(--text-dim); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
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
