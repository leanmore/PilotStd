<script setup lang="ts">
defineOptions({ name: 'StandardsStatusView' })
import { ref, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import { getStandardsStats, getStandardsStatus, type StandardStatusItem } from '@/api/standards'
import { getItem, setItem } from '@/lib/storage'

const stats = ref({ active: 0, inactive: 0, unknown: 0 })
const items = ref<StandardStatusItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const errMsg = ref('')

const filterStatus = ref<string | null>(null)
const filterStandardNo = ref('')
const filterName = ref('')

// 从 localStorage 恢复筛选条件
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

watch([filterStatus, filterStandardNo, filterName], saveFilters, { deep: true })

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

async function loadList() {
  loading.value = true
  errMsg.value = ''
  try {
    const r = await getStandardsStatus({
      page: page.value,
      page_size: pageSize,
      status: filterStatus.value || undefined,
      standard_no: filterStandardNo.value || undefined,
      name: filterName.value || undefined,
    })
    items.value = r.items
    total.value = r.total
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '加载失败'
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  loadList()
}

function onPageChange(p: number) {
  page.value = p
  loadList()
}

const totalPages = () => Math.max(1, Math.ceil(total.value / pageSize))
const pages = () => {
  const tp = totalPages()
  const p = page.value
  const range: number[] = []
  let start = Math.max(1, p - 2)
  const end = Math.min(tp, p + 2)
  if (end - start < 4) {
    if (start === 1) start = Math.max(1, end - 4)
    else start = Math.max(1, end - 4)
  }
  for (let i = start; i <= end; i++) range.push(i)
  return range
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

    <!-- 统计卡片 -->
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

    <!-- 筛选 -->
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

    <!-- 列表 -->
    <Card class="section">
      <template #content>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>

        <div class="table-meta">
          <span>共 {{ total }} 条记录</span>
          <span v-if="total > 0">第 {{ page }}/{{ totalPages() }} 页</span>
        </div>

        <table class="data-table" v-if="items.length">
          <thead>
            <tr>
              <th>标准号</th>
              <th>状态</th>
              <th>最后检查时间</th>
              <th>检查次数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td><strong>{{ item.standard_number }}</strong></td>
              <td><Tag :severity="statusSeverity(item.status)" :value="item.status" /></td>
              <td>{{ item.last_checked_at?.replace('T', ' ').substring(0, 16) || '—' }}</td>
              <td>{{ item.check_count }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="!loading" class="empty">暂无标准状态数据</p>

        <div class="pagination" v-if="totalPages() > 1">
          <Button icon="pi pi-angle-left" size="small" severity="secondary" text :disabled="page <= 1" @click="onPageChange(page - 1)" />
          <Button v-for="p in pages()" :key="p" :label="String(p)" size="small" :severity="p === page ? 'primary' : 'secondary'" text @click="onPageChange(p)" />
          <Button icon="pi pi-angle-right" size="small" severity="secondary" text :disabled="page >= totalPages()" @click="onPageChange(page + 1)" />
        </div>
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
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
.data-table th { font-weight: 600; color: var(--text-dim); font-size: 12px; text-transform: uppercase; }
.empty { color: var(--text-dim); font-size: 14px; padding: 20px 0; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 4px; margin-top: 12px; }
</style>
