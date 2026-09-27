<script setup lang="ts">
defineOptions({ name: 'FavoritesView' })
// FavoritesView.vue — 收藏列表页（批次7：Tab 分类切换 + 类型标签 + 导出）
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import FavoriteStatusTag from '@/components/FavoriteStatusTag.vue'

const { t } = useI18n()
const toast = useToast()

interface FavoriteItem {
  id: number
  standard_number: string
  std_name: string | null
  standard_type: string
  status: string
  local_path: string | null
  publish_date: string | null
  created_at: string
  updated_at: string
  source_site: string | null
  // 下载队列四字段（favorite_downloads）：null 表示收藏存在但队列行缺失 → 展示为"未加入队列"
  download_status: string | null
  download_error: string | null
  last_attempt: string | null
  download_updated_at: string | null
}

const favorites = ref<FavoriteItem[]>([])
const loading = ref(false)
const activeType = ref<'all' | string>('all')

// Tab 定义：全部 + 三类 + 其他（unknown/enterprise/group/foreign 归入"其他"）
const typeTabs = [
  { key: 'all', labelKey: 'favorites.type.all' },
  { key: 'NationalStd', labelKey: 'favorites.type.national', severity: 'info' },
  { key: 'IndustryStd', labelKey: 'favorites.type.industry', severity: 'warning' },
  { key: 'LocalStd', labelKey: 'favorites.type.local', severity: 'success' },
  { key: 'other', labelKey: 'favorites.type.other', severity: 'secondary' },
]

// 存 key、渲染期翻译（模块级表不能在模块作用域求值一次 t()）
const STD_TYPE_LABEL_KEY: Record<string, string> = {
  NationalStd: 'favorites.type.national', IndustryStd: 'favorites.type.industry', LocalStd: 'favorites.type.local',
  enterprise: 'favorites.type.enterprise', group: 'favorites.type.group', foreign: 'favorites.type.foreign', Unknown: 'favorites.type.unknown',
}
const STD_TYPE_SEVERITY: Record<string, string> = {
  NationalStd: 'info', IndustryStd: 'warning', LocalStd: 'success',
  enterprise: 'secondary', group: 'secondary', foreign: 'secondary', Unknown: 'secondary',
}

function isOther(st: string): boolean {
  return !['NationalStd', 'IndustryStd', 'LocalStd'].includes(st)
}

const filtered = computed(() => {
  if (activeType.value === 'all') return favorites.value
  if (activeType.value === 'other') return favorites.value.filter((f) => isOther(f.standard_type))
  return favorites.value.filter((f) => f.standard_type === activeType.value)
})

// Tab 标题里的分类计数：与 filtered 同口径（判定逻辑只此一份，避免两处漂移）
function countOf(key: string): number {
  if (key === 'all') return favorites.value.length
  if (key === 'other') return favorites.value.filter((f) => isOther(f.standard_type)).length
  return favorites.value.filter((f) => f.standard_type === key).length
}

async function loadFavorites() {
  loading.value = true
  try {
    const resp = await fetch('/api/favorites', { credentials: 'include' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    favorites.value = data.favorites || []
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('favorites.load_failed'), detail: String(e?.message || e), life: 3000 })
  } finally {
    loading.value = false
  }
}

async function exportFavorites(scope: 'current' | 'all') {
  const params = new URLSearchParams({ format: 'csv' })
  // 导出当前分类：activeType 为具体类型或 other（other 无直接后端筛选，导出全部后由客户端理解）
  if (scope === 'current' && ['NationalStd', 'IndustryStd', 'LocalStd'].includes(activeType.value)) {
    params.set('standard_type', activeType.value)
  }
  try {
    const resp = await fetch(`/api/favorites/export?${params.toString()}`, { credentials: 'include' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `favorites${activeType.value === 'all' ? '' : `-${activeType.value}`}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('favorites.export_failed'), detail: String(e?.message || e), life: 3000 })
  }
}

onMounted(loadFavorites)
</script>

<template>
  <div class="favorites-view">
    <div class="header">
      <h2>{{ t('nav.favorites') }}</h2>
      <div class="export-actions">
        <Button :label="t('favorites.export_current')" icon="pi pi-download" size="small" severity="secondary"
          :disabled="filtered.length === 0" @click="exportFavorites('current')" />
        <Button :label="t('favorites.export_all')" icon="pi pi-file-export" size="small" severity="secondary"
          :disabled="favorites.length === 0" @click="exportFavorites('all')" />
      </div>
    </div>

    <!-- lazy：非活动分类不渲染表格。否则 5 个面板都会把 DataTable 建出来（104 条收藏 → 520 行 DOM） -->
    <Tabs v-model:value="activeType" lazy>
      <TabList>
        <Tab v-for="tab in typeTabs" :key="tab.key" :value="tab.key">
          {{ `${t(tab.labelKey)} (${countOf(tab.key)})` }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="tab in typeTabs" :key="tab.key" :value="tab.key">
          <DataTable :value="filtered" :loading="loading" striped-rows size="small" dataKey="id">
            <Column field="standard_number" :header="t('favorites.col_standard_number')" style="min-width: 180px" />
            <Column field="std_name" :header="t('favorites.col_name')" style="min-width: 220px" />
            <Column :header="t('favorites.col_type')" style="width: 110px">
              <template #body="{ data }">
                <Tag :value="t(STD_TYPE_LABEL_KEY[data.standard_type] || 'favorites.type.unknown')"
                  :severity="STD_TYPE_SEVERITY[data.standard_type] || 'secondary'" />
              </template>
            </Column>
            <Column :header="t('favorites.col_status')" style="width: 13rem">
              <template #body="{ data }">
                <!-- 下载状态标签 + 失败原因（展示截断 120 字符，悬停看全量与最后尝试时间） -->
                <FavoriteStatusTag :status="data" show-error />
              </template>
            </Column>
            <Column field="publish_date" :header="t('favorites.col_publish_date')" style="width: 120px">
              <template #body="{ data }">{{ data.publish_date || '-' }}</template>
            </Column>
            <Column field="created_at" :header="t('favorites.col_created_at')" style="width: 160px">
              <template #body="{ data }">{{ (data.created_at || '').replace('T', ' ').slice(0, 16) }}</template>
            </Column>
          </DataTable>
          <div v-if="!loading && filtered.length === 0" class="empty">
            {{ activeType === 'all' ? t('favorites.empty') : t('favorites.empty_type') }}
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
.favorites-view { padding: 1rem; max-width: 1200px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.export-actions { display: flex; gap: 0.5rem; }
.empty { padding: 2rem; text-align: center; color: var(--text-dim); }
</style>
