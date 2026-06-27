<script setup lang="ts">
defineOptions({ name: 'NotificationLogsView' })
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import { getNotificationLogs, type NotificationLog } from '@/api/notification'

const logs = ref<NotificationLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const errMsg = ref('')

// 筛选
const filterChannel = ref<string | null>(null)
const filterStatus = ref<string | null>(null)
const filterStartDate = ref('')
const filterEndDate = ref('')

// 详情弹窗
const detailVisible = ref(false)
const detailItem = ref<NotificationLog | null>(null)

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
    check_batch_complete: '批次完成', test: '测试',
  }
  return m[v] || v
}

async function loadLogs() {
  loading.value = true
  errMsg.value = ''
  try {
    const r = await getNotificationLogs({
      page: page.value,
      page_size: pageSize,
      channel: filterChannel.value || undefined,
      status: filterStatus.value || undefined,
      start_date: filterStartDate.value || undefined,
      end_date: filterEndDate.value || undefined,
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
  filterStartDate.value = ''
  filterEndDate.value = ''
  page.value = 1
  loadLogs()
}

function onPageChange(p: number) {
  page.value = p
  loadLogs()
}

function showDetail(item: NotificationLog) {
  detailItem.value = item
  detailVisible.value = true
}

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

onMounted(loadLogs)
</script>

<template>
  <div class="page">
    <h2 class="page-title">通知日志</h2>

    <Card class="section">
      <template #content>
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
            <label>开始日期</label>
            <InputText v-model="filterStartDate" type="date" />
          </div>
          <div class="filter-item">
            <label>结束日期</label>
            <InputText v-model="filterEndDate" type="date" />
          </div>
          <div class="filter-actions">
            <Button icon="pi pi-search" label="查询" size="small" @click="onSearch" />
            <Button icon="pi pi-refresh" label="重置" size="small" severity="secondary" @click="onReset" />
          </div>
        </div>
      </template>
    </Card>

    <Card class="section">
      <template #content>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>

        <div class="table-meta">
          <span>共 {{ total }} 条记录</span>
          <span v-if="total > 0">第 {{ page }}/{{ totalPages() }} 页</span>
        </div>

        <table class="log-table" v-if="logs.length">
          <thead>
            <tr>
              <th>时间</th>
              <th>渠道</th>
              <th>事件</th>
              <th>状态</th>
              <th>标题</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td>{{ l.sent_at?.replace('T', ' ').substring(0, 16) }}</td>
              <td>{{ channelLabel(l.channel) }}</td>
              <td>{{ eventLabel(l.event_type) }}</td>
              <td><Tag :severity="statusSeverity(l.status)" :value="l.status === 'success' ? '成功' : '失败'" /></td>
              <td class="title-cell">{{ l.title }}</td>
              <td><Button label="查看" size="small" severity="secondary" text @click="showDetail(l)" /></td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="!loading" class="empty">暂无通知记录</p>

        <div class="pagination" v-if="totalPages() > 1">
          <Button icon="pi pi-angle-left" size="small" severity="secondary" text :disabled="page <= 1" @click="onPageChange(page - 1)" />
          <Button v-for="p in pages()" :key="p" :label="String(p)" size="small" :severity="p === page ? 'primary' : 'secondary'" text @click="onPageChange(p)" />
          <Button icon="pi pi-angle-right" size="small" severity="secondary" text :disabled="page >= totalPages()" @click="onPageChange(page + 1)" />
        </div>
      </template>
    </Card>

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
  </div>
</template>

<style scoped>
.page { max-width: 1000px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.section { margin-bottom: 16px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
.filter-item { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
.filter-item label { font-size: 12px; font-weight: 500; color: var(--text-dim); }
.filter-actions { display: flex; gap: 8px; align-items: flex-end; padding-bottom: 1px; }
.table-meta { display: flex; justify-content: space-between; font-size: 13px; color: var(--text-dim); margin-bottom: 10px; }
.log-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.log-table th, .log-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
.log-table th { font-weight: 600; color: var(--text-dim); font-size: 12px; text-transform: uppercase; }
.title-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { color: var(--text-dim); font-size: 14px; padding: 20px 0; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 4px; margin-top: 12px; }
.detail { display: flex; flex-direction: column; gap: 10px; }
.detail-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.detail-row span:first-child { color: var(--text-dim); }
.detail-body { font-size: 13px; }
.detail-body span { color: var(--text-dim); }
.detail-body pre { margin: 4px 0 0; padding: 8px; background: var(--bg); border-radius: 4px; font-size: 12px; white-space: pre-wrap; }
.err { color: var(--danger) !important; }
</style>
