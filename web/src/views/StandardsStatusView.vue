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
import { getStandardsStats, getStandardsStatus, type StandardStatusItem } from '@/api/standards'
import { getItem, setItem } from '@/lib/storage'
import { useIncrementalScroll } from '@/composables/useIncrementalScroll'
import TableLoadFooter from '@/components/TableLoadFooter.vue'

const MAX_SIZE = 150

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

// 筛选条件变化时持久化 + 重新加载（useIncrementalScroll 内部 watch 自动重置首屏）
watch([filterStatus, filterStandardNo, filterName], () => {
  saveFilters()
  loadList()
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
    stats.value = await getStandardsStats()
  } catch { /* 统计失败不影响列表 */ }
}

// 增量滚动控制
const {
  displayRecords,
  isLoadingMore,
  showLoadAllButton,
  loadAllRemaining,
} = useIncrementalScroll(allItems)

async function loadList() {
  loading.value = true
  errMsg.value = ''
  try {
    const r = await getStandardsStatus({
      page: 1,
      page_size: MAX_SIZE,
      status: filterStatus.value || undefined,
      standard_no: filterStandardNo.value || undefined,
      name: filterName.value || undefined,
    })
    allItems.value = r.items
    total.value = r.total
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '加载失败'
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
          <Column field="standard_name" header="标准名称" style="min-width: 18rem">
            <template #body="{ data }">
              {{ data.standard_name || '—' }}
            </template>
          </Column>
          <Column field="status" header="状态" style="width: 8rem">
            <template #body="{ data }">
              <Tag :severity="statusSeverity(data.status)" :value="data.status" />
            </template>
          </Column>
        </DataTable>

        <p v-if="!loading && displayRecords.length === 0" class="empty">暂无标准状态数据</p>

        <TableLoadFooter
          v-if="total > 0"
          :displayed="displayRecords.length"
          :total="Math.min(total, MAX_SIZE)"
          :is-loading="isLoadingMore"
          :show-load-all-button="showLoadAllButton"
          @load-all="loadAllRemaining"
        />
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
