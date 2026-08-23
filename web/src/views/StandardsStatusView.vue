<script setup lang="ts">
defineOptions({ name: 'StandardsStatusView' })
import { ref, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { getStandardsStats, getStandardsStatus, clearStandardsStatusCache, type StandardStatusItem } from '@/api/standards'
import { getItem, setItem } from '@/lib/storage'
import { useIncrementalScroll, type PaginatedResult } from '@/composables/useIncrementalScroll'
import TableLoadFooter from '@/components/TableLoadFooter.vue'

const MAX_SIZE = 100

const stats = ref({ active: 0, inactive: 0, unknown: 0 })
const allItems = ref<StandardStatusItem[]>([])
const total = ref(0)
const loading = ref(false)
const errMsg = ref('')

const filterStatus = ref<string | null>(null)
const filterStandardNo = ref('')
const filterName = ref('')

function loadFilters() {
  try {
    const raw = getItem('standards_filters')
    if (raw) {
      const f = JSON.parse(raw)
      filterStatus.value = f.s ?? null
      filterStandardNo.value = f.n ?? ''
      filterName.value = f.m ?? ''
    }
  } catch { /* ignore */ }
}

function saveFilters() {
  setItem('standards_filters', JSON.stringify({
    s: filterStatus.value, n: filterStandardNo.value, m: filterName.value,
  }))
}

// 筛选条件变化时持久化 + 清除缓存 + 重新加载（分页模式重拉第一页；降级模式走全量）
watch([filterStatus, filterStandardNo, filterName], () => {
  saveFilters()
  clearStandardsStatusCache()
  if (usePaginated) {
    reloadRecords()
  } else {
    loadList()
  }
})

const statusOptions = [
  { label: '全部', value: null },
  { label: '现行', value: '现行' },
  { label: '已废止', value: '已废止' },
  { label: '未知', value: '未知' },
]

function statusSeverity(s: string): 'success' | 'danger' | 'info' | 'secondary' {
  if (s === '现行') return 'success'
  if (s === '已废止') return 'danger'
  if (s === '未知') return 'secondary'
  return 'info'
}

async function loadStats() {
  try {
    stats.value = await getStandardsStats('/standards-status')
  } catch { /* 统计失败不影响列表 */ }
}

// 增量滚动控制（方案 C：IntersectionObserver 监听哨兵元素）
// Phase 2 分页化：VITE_USE_PAGINATED_RECORDS_API=true 时走分页端点，否则全量前端分片
const usePaginated = import.meta.env.VITE_USE_PAGINATED_RECORDS_API === 'true'
const sentinel = ref<HTMLElement | null>(null)

/** 分页模式 fetcher：包装 /standards-status 为 PaginatedResult 结构 */
async function fetchStandardsPage(page: number, pageSize: number): Promise<PaginatedResult> {
  const r = await getStandardsStatus({
    page,
    page_size: pageSize,
    status: filterStatus.value || undefined,
    standard_no: filterStandardNo.value || undefined,
    name: filterName.value || undefined,
  }, '/standards-status')
  total.value = r.total // 分页模式同步总条数（降级模式由 loadList 设置）
  return {
    items: r.items,
    total: r.total,
    page,
    pageSize,
    hasMore: page * pageSize < r.total,
  }
}

const {
  displayRecords,
  isLoadingMore,
  showLoadAllButton,
  loadAllRemaining,
  reload: reloadRecords,
} = useIncrementalScroll(usePaginated ? fetchStandardsPage : allItems, sentinel)

async function loadList() {
  if (usePaginated) return // 分页模式：数据由 useIncrementalScroll 的 fetcher 按页拉取
  loading.value = true
  errMsg.value = ''
  try {
    const r = await getStandardsStatus({
      page: 1,
      page_size: MAX_SIZE,
      status: filterStatus.value || undefined,
      standard_no: filterStandardNo.value || undefined,
      name: filterName.value || undefined,
    }, '/standards-status')
    allItems.value = r.items
    total.value = r.total
  } catch (e: any) {
    // FastAPI 422 校验错误在 detail 数组而非 error 字段，需优先解析 detail[0].msg
    errMsg.value = e.response?.data?.detail?.[0]?.msg
      || e.response?.data?.error
      || '加载失败'
  } finally {
    loading.value = false
  }
}

function onSearch() {
  loadList()
}

onMounted(() => {
  loadFilters()
  loadStats()
  loadList()
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">标准状态</h2>

    <div class="stats-row">
      <Card class="stat-card active">
        <template #content>
          <div class="stat-num">{{ stats.active }}</div>
          <div class="stat-label">📗 现行</div>
        </template>
      </Card>
      <Card class="stat-card inactive">
        <template #content>
          <div class="stat-num">{{ stats.inactive }}</div>
          <div class="stat-label">📕 已废止</div>
        </template>
      </Card>
      <Card class="stat-card unknown">
        <template #content>
          <div class="stat-num">{{ stats.unknown }}</div>
          <div class="stat-label">⚪ 未知</div>
        </template>
      </Card>
    </div>

    <Card class="section">
      <template #content>
        <div class="filter-row">
          <div class="filter-item">
            <label>状态</label>
            <Select v-model="filterStatus" :options="statusOptions" optionLabel="label" optionValue="value" />
          </div>
          <div class="filter-item">
            <label>标准号</label>
            <InputText v-model="filterStandardNo" placeholder="如 GB/T" />
          </div>
          <div class="filter-item">
            <label>名称</label>
            <InputText v-model="filterName" placeholder="关键词" />
          </div>
          <div class="filter-actions">
            <Button icon="pi pi-search" label="查询" size="small" @click="onSearch" />
            <Button icon="pi pi-refresh" label="刷新" size="small" severity="secondary" @click="clearStandardsStatusCache(); loadList()" />
          </div>
        </div>
      </template>
    </Card>

    <Card class="section">
      <template #content>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>

        <div class="table-meta">
          <span>共 {{ total }} 条记录</span>
          <span v-if="displayRecords.length > 0 && displayRecords.length < total">
            已显示 {{ displayRecords.length }} / {{ total }} 条
          </span>
        </div>

        <DataTable
          :value="displayRecords"
          :loading="loading"
          stripedRows
          size="small"
          dataKey="id"
        >
          <Column field="standard_number" header="标准号" style="min-width: 12rem">
            <template #body="{ data }">
              <strong>{{ data.standard_number }}</strong>
            </template>
          </Column>
          <Column field="std_name" header="标准名称" style="min-width: 18rem">
            <template #body="{ data }">
              {{ data.std_name || '—' }}
            </template>
          </Column>
          <Column field="status" header="状态" style="width: 8rem">
            <template #body="{ data }">
              <Tag :severity="statusSeverity(data.status)" :value="data.status" />
            </template>
          </Column>
          <Column field="last_checked_at" header="最后检查时间" style="width: 10rem">
            <template #body="{ data }">
              {{ data.last_checked_at ? data.last_checked_at.substring(0, 10) : '—' }}
            </template>
          </Column>
          <Column field="check_count" header="检查次数" style="width: 6rem; text-align: right" />
        </DataTable>

        <p v-if="!loading && displayRecords.length === 0" class="empty">暂无标准状态数据</p>

        <TableLoadFooter
          v-if="total > 0"
          :displayed="displayRecords.length"
          :total="usePaginated ? total : Math.min(total, MAX_SIZE)"
          :is-loading="isLoadingMore"
          :show-load-all-button="showLoadAllButton"
          @load-all="loadAllRemaining"
        />
        <!-- 滚动加载哨兵：进入视口前 100px 触发下一批加载（方案 C，不占视觉空间） -->
        <div ref="sentinel" class="scroll-sentinel" style="height: 1px; opacity: 0;" aria-hidden="true" />
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 1000px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-card.active { border-left: 4px solid var(--green-500, #22c55e); }
.stat-card.inactive { border-left: 4px solid var(--red-500, #ef4444); }
.stat-card.unknown { border-left: 4px solid var(--gray-400, #9ca3af); }
.stat-num { font-size: 28px; font-weight: 700; }
.stat-label { font-size: 13px; color: var(--text-dim); margin-top: 4px; }
.section { margin-bottom: 16px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
.filter-item { display: flex; flex-direction: column; gap: 4px; min-width: 140px; }
.filter-item label { font-size: 12px; font-weight: 500; color: var(--text-dim); }
.filter-actions { display: flex; gap: 8px; align-items: flex-end; padding-bottom: 1px; }
.table-meta { display: flex; justify-content: space-between; font-size: 13px; color: var(--text-dim); margin-bottom: 10px; }
.empty { color: var(--text-dim); font-size: 14px; padding: 20px 0; }
</style>
