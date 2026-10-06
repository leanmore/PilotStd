<script setup lang="ts">
defineOptions({ name: 'NotificationLogsView' })
// T-41 前端子批：script 逻辑已抽到 `@/composables/useNotificationLogs`（见该文件头部说明）。
// 这里只做「装配 + 解构」：**只解构模板实际用到的名字**（其余留在 composable 内部，TS 不再报未使用）。
import { useI18n } from 'vue-i18n'
import { useNotificationLogs } from '@/composables/useNotificationLogs'

const { t } = useI18n()
const {
  logs,
  total,
  page,
  loading,
  errMsg,
  tableHeight,
  onResizeStart,
  filterChannel,
  filterStatus,
  filterStartDate,
  filterEndDate,
  detailVisible,
  detailItem,
  failedItems,
  failedTotal,
  failedPage,
  failedPageSize,
  failedLoaded,
  failedError,
  loadFailedItems,
  errorTypeLabel,
  cleanupVisible,
  cleanupDays,
  cleanupLoading,
  cleanupResult,
  doCleanup,
  channelOptions,
  statusOptions,
  channelLabel,
  statusSeverity,
  statusLabel,
  eventLabel,
  loadLogs,
  onSearch,
  onReset,
  onPageChange,
  showDetail,
  rowClass,
  totalPages,
  pages,
} = useNotificationLogs()
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

        <!-- P3：失败明细（**按需加载 + 自身分页 + 服务端已脱敏**；文案键与通知配置页共用 notification.config 命名空间） -->
        <div v-if="detailItem.failed_count > 0" class="failed-items">
          <Button
            :label="t('notification.config.failed_items.open')"
            size="small"
            severity="secondary"
            text
            @click="loadFailedItems(1)"
          />
          <p v-if="failedError" class="err" style="margin:6px 0 0">{{ t('notification.config.failed_items.load_failed') }}</p>
          <div v-else-if="failedLoaded" style="margin-top:6px">
            <p style="font-size:12px;color:var(--text-dim);margin:0 0 6px">
              {{ t('notification.config.failed_items.title') }} · {{ t('notification.config.failed_items.total', { total: failedTotal }) }}
            </p>
            <table v-if="failedItems.length" class="failed-table">
              <thead>
                <tr>
                  <th>{{ t('notification.config.failed_items.col_number') }}</th>
                  <th>{{ t('notification.config.failed_items.col_name') }}</th>
                  <th>{{ t('notification.config.failed_items.col_type') }}</th>
                  <th>{{ t('notification.config.failed_items.col_message') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(it, idx) in failedItems" :key="idx">
                  <td>{{ it.standard_number }}</td>
                  <td>{{ it.standard_name }}</td>
                  <!-- 技术枚举**必须翻译**后展示；未知取值回退 unknown 文案（不暴露原始码） -->
                  <td>{{ errorTypeLabel(it.error_type) }}</td>
                  <td class="err">{{ it.error_message }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else style="font-size:12px;color:var(--text-dim)">{{ t('notification.config.failed_items.empty') }}</p>
            <div v-if="failedTotal > failedPageSize" style="display:flex;gap:8px;align-items:center;margin-top:6px">
              <Button label="‹" size="small" text :disabled="failedPage <= 1" @click="loadFailedItems(failedPage - 1)" />
              <span style="font-size:12px;color:var(--text-dim)">{{ failedPage }}</span>
              <Button
                label="›"
                size="small"
                text
                :disabled="failedPage * failedPageSize >= failedTotal"
                @click="loadFailedItems(failedPage + 1)"
              />
            </div>
          </div>
        </div>
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
