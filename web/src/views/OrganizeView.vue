<script setup lang="ts">
defineOptions({ name: 'OrganizeView' })
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getFiles, postCleanEmpty } from '@/api'
import { enqueueValidityCheck } from '@/api/validity'
import { getItem, setItem } from '@/lib/storage'
import { useAppStore } from '@/stores/app'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import Tag from 'primevue/tag'
import LogBar from '@/components/LogBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'

const { t } = useI18n()
const appStore = useAppStore()
const canEnqueue = computed(() => appStore.role === 'admin')

const rootPath = ref('/standards')
const files = ref<any[]>([])
const loading = ref(false)
const cleanResult = ref('')
const error = ref('')

async function browse(dir?: string) {
  const p = dir || rootPath.value
  loading.value = true; error.value = ''
  try {
    const data = await getFiles(p, '/organize')
    files.value = (data.files || []).map((f: any) => ({
      ...f, _size: f.size ? (f.size > 1048576 ? (f.size/1048576).toFixed(1)+' MB' : (f.size/1024).toFixed(0)+' KB') : ''
    }))
    rootPath.value = p
  } catch (e: any) { error.value = e.response?.data?.error || t('organize.browse_failed') }
  finally { loading.value = false }
}

async function cleanEmpty() {
  // 2026-11-25 修复：原实现无 try/catch —— 清理失败时产生未捕获 Promise rejection，
  // 用户也得不到任何提示。
  try {
    const data = await postCleanEmpty(rootPath.value)
    cleanResult.value = data.removed ? t('organize.cleaned', { n: data.removed }) : t('organize.no_empty_dirs')
    setTimeout(() => cleanResult.value = '', 3000)
    await browse()
  } catch (e: any) {
    error.value = e.response?.data?.error || t('organize.clean_failed')
  }
}

// ── 文件选择 + 入队 ──
const selectedFiles = ref<Set<string>>(new Set())
const enqueueResult = ref('')
const enqueueLoading = ref(false)

// 当前页的文件路径列表（用于全选）
const currentPagePaths = computed(() => paginatedFiles.value.filter((f: any) => f.type !== 'dir').map((f: any) => f.path))

function isFileSelected(path: string): boolean {
  return selectedFiles.value.has(path)
}

function toggleFile(path: string) {
  const s = new Set(selectedFiles.value)
  if (s.has(path)) s.delete(path); else s.add(path)
  selectedFiles.value = s
}

function toggleAll() {
  const s = new Set(selectedFiles.value)
  const allSelected = currentPagePaths.value.every(p => s.has(p))
  if (allSelected) {
    for (const p of currentPagePaths.value) s.delete(p)
  } else {
    for (const p of currentPagePaths.value) s.add(p)
  }
  selectedFiles.value = s
}

function isAllSelected(): boolean {
  if (currentPagePaths.value.length === 0) return false
  return currentPagePaths.value.every(p => selectedFiles.value.has(p))
}

async function doEnqueue() {
  if (selectedFiles.value.size === 0) return
  enqueueLoading.value = true; enqueueResult.value = ''
  try {
    const r = await enqueueValidityCheck(Array.from(selectedFiles.value))
    enqueueResult.value = t('organize.enqueued', { n: r.enqueued, m: r.total })
    selectedFiles.value = new Set()
    setTimeout(() => enqueueResult.value = '', 3000)
  } catch (e: any) {
    enqueueResult.value = t('organize.enqueue_failed', { msg: e.response?.data?.error || e.message })
  } finally {
    enqueueLoading.value = false
  }
}

onMounted(() => browse())

const page = ref(Number(getItem('organize_page')) || 0)
const rows = ref(30)

const paginatedFiles = computed(() => {
  const start = page.value * rows.value
  return files.value.slice(start, start + rows.value)
})

function onPage(e: any) {
  page.value = e.page
  setItem('organize_page', String(e.page))
}

// 面包屑：当前路径拆成逐段可点击的导航
const breadcrumbs = computed(() => {
  const p = rootPath.value.replace(/\\/g, '/')
  const parts = p.split('/').filter(Boolean)
  const items: { label: string; path: string }[] = []
  let acc = ''
  for (const part of parts) {
    acc += '/' + part
    items.push({ label: part, path: acc })
  }
  return items
})
</script>

<template>
  <h1>{{ t('organize.title') }}</h1>
  <p class="hint">{{ t('organize.hint') }}</p>

  <!-- 控制区卡片 -->
  <div class="card mt-2">
    <div class="controls">
      <!-- 两路事件语义都必须保留（原生 <input> 的形态）：
           @keyup.enter 直接拿输入框当前值去 browse；@change 把值写回 rootPath（失焦/回车提交时同步）。
           AppInput 透传 $attrs，故两个监听都落在底层 <input> 上。 -->
      <AppInput
        :model-value="rootPath"
        size="m"
        class="fi"
        style="flex:1"
        placeholder="/standards"
        @keyup.enter="browse(($event.target as any).value)"
        @change="(e: Event) => rootPath = (e.target as any).value"
      />
<AppButton
        :label="t('organize.browse')"
        icon="pi pi-folder-open"
        :loading="loading"
        @click="browse()"
        size="s"
        type="secondary"
      />
      <AppButton
        :label="t('organize.clean_empty')"
        icon="pi pi-trash"
        type="danger"
        size="s"
        @click="cleanEmpty"
      />
    </div>
    <p v-if="cleanResult" class="clean-msg">{{ cleanResult }}</p>
    <p v-if="error" class="err-msg">{{ error }}</p>
  </div>

  <!-- 面包屑导航 -->
  <div class="breadcrumb mt-2">
    <span class="crumb" @click="browse('/')">{{ t('organize.root') }}</span>
    <template v-for="(c, i) in breadcrumbs" :key="c.path">
      <span class="crumb-sep">›</span>
      <span class="crumb" :class="{ active: i === breadcrumbs.length - 1 }" @click="browse(c.path)">{{ c.label }}</span>
    </template>
  </div>

  <!-- 统计 + 操作栏 -->
  <div class="stats-row mt-2">
    <Tag severity="info" :value="t('organize.files', { n: files.length })" />
    <Tag severity="success" :value="files.filter(f=>f.type==='pdf').length + ' PDF'" />
    <Tag severity="warn" :value="t('organize.other', { n: files.filter(f=>f.type!=='pdf').length })" />
    <div style="flex:1" />
    <div v-if="canEnqueue && selectedFiles.size > 0" class="op-bar">
      <span class="selected-count">{{ t('organize.selected', { n: selectedFiles.size }) }}</span>
<AppButton
        :label="t('organize.enqueue_validity')"
        icon="pi pi-clock"
        :loading="enqueueLoading"
        @click="doEnqueue"
        size="s"
        type="secondary"
      />
    </div>
    <span v-if="enqueueResult" class="enqueue-msg">{{ enqueueResult }}</span>
  </div>

  <!-- 文件列表 -->
  <DataView :value="paginatedFiles" size="small" class="mt-2">
    <template #list="slotProps">
      <!-- 全选行 -->
      <div v-if="canEnqueue" class="select-all-row">
        <AppCheckbox :model-value="isAllSelected()" @change="toggleAll" :input-id="'select-all'" />
        <label for="select-all" class="select-all-label">{{ t('organize.select_all') }}</label>
      </div>
      <div v-for="item in slotProps.items" :key="item.path" class="p-2 border-bottom">
        <div
          style="display:flex;gap:var(--space-12);padding:var(--space-6) 0;border-bottom:1px solid var(--border-light);align-items:center"
          :class="{ 'dir-row': item.type === 'dir' }"
          :style="item.type === 'dir' ? 'cursor:pointer' : ''"
          @click="item.type === 'dir' ? browse(item.path) : undefined"
        >
          <AppCheckbox
            v-if="item.type !== 'dir' && canEnqueue"
            :model-value="isFileSelected(item.path)"
            @change="toggleFile(item.path)"
          />
          <span v-else style="width:20px;flex-shrink:0" />
          <span style="min-width:140px;font-weight:var(--font-weight-medium);flex-shrink:0">{{ item.name }}</span>
          <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:var(--font-size-13);color:var(--text-dim)">{{ item.path }}</span>
          <span style="min-width:80px;font-size:var(--font-size-12);color:var(--text-dim);flex-shrink:0">{{ item._size }}</span>
          <span style="min-width:60px;flex-shrink:0">
            <Tag :value="item.type" :severity="item.type==='pdf'?'success':'info'" />
          </span>
        </div>
      </div>
    </template>
  </DataView>
  <!-- 修 2026-11-24（P0-3 同类）：`:first` 必须受控，否则从存储恢复的 page 与
       Paginator 内部索引错位（内容已是第 N 页、高亮仍停在第 1 页）。 -->
  <Paginator :first="page * rows" :rows="rows" :totalRecords="files.length" @page="onPage" class="mt-2" />
  <LogBar />
</template>

<style scoped>
.controls { display: flex; gap: var(--space-8); align-items: center; flex-wrap: wrap; }
/* 布局只留伸缩与最小宽度；边框/底色/四态由 <AppInput size="m"> 承担（ui-system.md §11.4） */
.fi { flex: 1; min-width: 200px; }

.breadcrumb { display: flex; align-items: center; gap: var(--space-4); font-size: var(--font-size-13); flex-wrap: wrap; }
.crumb { color: var(--primary); cursor: pointer; padding: var(--space-2) var(--space-6); border-radius: var(--ds-radius-xs); transition: background 0.15s; }
.crumb:hover { background: var(--primary-bg); }
.crumb.active { color: var(--text-heading); font-weight: var(--font-weight-semibold); cursor: default; }
.crumb.active:hover { background: none; }
.crumb-sep { color: var(--text-dim); font-size: var(--font-size-11); user-select: none; }
.dir-row:hover { background: var(--selected); }
.clean-msg { font-size: var(--font-size-12); color: var(--success); margin-top: var(--space-6); }
.err-msg { color: var(--danger); font-size: var(--font-size-12); margin-top: var(--space-6); }
.stats-row { display: flex; gap: var(--space-8); flex-wrap: wrap; align-items: center; }
.op-bar { display: flex; align-items: center; gap: var(--space-8); }
.selected-count { font-size: var(--font-size-12); color: var(--primary); font-weight: var(--font-weight-medium); }
.enqueue-msg { font-size: var(--font-size-12); color: var(--success); }
.select-all-row { display: flex; align-items: center; gap: var(--space-8); padding: var(--space-6) var(--space-12); background: var(--surface-raised); border-bottom: 1px solid var(--border); }
.select-all-label { font-size: var(--font-size-12); color: var(--text-secondary); cursor: pointer; }
.border-bottom { border-bottom: 1px solid var(--border-light); }
</style>
