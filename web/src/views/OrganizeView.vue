<script setup lang="ts">
defineOptions({ name: 'OrganizeView' })
import { ref, onMounted, computed } from 'vue'
import { getFiles, postCleanEmpty } from '@/api'
import { enqueueValidityCheck } from '@/api/validity'
import { getItem, setItem } from '@/lib/storage'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import Tag from 'primevue/tag'
import LogBar from '@/components/LogBar.vue'

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
  } catch (e: any) { error.value = e.response?.data?.error || '浏览失败，请检查路径和权限' }
  finally { loading.value = false }
}

async function cleanEmpty() {
  const data = await postCleanEmpty(rootPath.value)
  cleanResult.value = data.removed ? `已清理 ${data.removed} 个空目录` : '无空目录'
  setTimeout(() => cleanResult.value = '', 3000)
  browse()
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
    enqueueResult.value = `已加入队列：${r.enqueued}/${r.total}`
    selectedFiles.value = new Set()
    setTimeout(() => enqueueResult.value = '', 3000)
  } catch (e: any) {
    enqueueResult.value = `入队失败: ${e.response?.data?.error || e.message}`
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
  <h1>文件管理</h1>
  <p class="hint">浏览和管理标准库中的文件，支持清理空目录。</p>

  <!-- 控制区卡片 -->
  <div class="card mt-2">
    <div class="controls">
      <input :value="rootPath" @keyup.enter="browse(($event.target as any).value)" @change="e => rootPath = (e.target as any).value" class="fi" style="flex:1" placeholder="/standards" />
      <Button label="浏览" icon="pi pi-folder-open" :loading="loading" @click="browse()" size="small" />
      <Button label="清理空目录" icon="pi pi-trash" severity="warn" size="small" @click="cleanEmpty" />
    </div>
    <p v-if="cleanResult" class="clean-msg">{{ cleanResult }}</p>
    <p v-if="error" class="err-msg">{{ error }}</p>
  </div>

  <!-- 面包屑导航 -->
  <div class="breadcrumb mt-2">
    <span class="crumb" @click="browse('/')">根目录</span>
    <template v-for="(c, i) in breadcrumbs" :key="c.path">
      <span class="crumb-sep">›</span>
      <span class="crumb" :class="{ active: i === breadcrumbs.length - 1 }" @click="browse(c.path)">{{ c.label }}</span>
    </template>
  </div>

  <!-- 统计 + 操作栏 -->
  <div class="stats-row mt-2">
    <Tag severity="info" :value="files.length + ' 个文件'" />
    <Tag severity="success" :value="files.filter(f=>f.type==='pdf').length + ' PDF'" />
    <Tag severity="warn" :value="files.filter(f=>f.type!=='pdf').length + ' 其他'" />
    <div style="flex:1" />
    <div v-if="selectedFiles.size > 0" class="op-bar">
      <span class="selected-count">已选 {{ selectedFiles.size }} 个文件</span>
      <Button label="加入时效性检查" icon="pi pi-clock" size="small" :loading="enqueueLoading" @click="doEnqueue" />
    </div>
    <span v-if="enqueueResult" class="enqueue-msg">{{ enqueueResult }}</span>
  </div>

  <!-- 文件列表 -->
  <DataView :value="paginatedFiles" size="small" class="mt-2">
    <template #list="slotProps">
      <!-- 全选行 -->
      <div class="select-all-row">
        <Checkbox :model-value="isAllSelected()" @change="toggleAll" :input-id="'select-all'" />
        <label for="select-all" class="select-all-label">全选本页文件</label>
      </div>
      <div v-for="item in slotProps.items" :key="item.path" class="p-2 border-bottom">
        <div
          style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-light);align-items:center"
          :class="{ 'dir-row': item.type === 'dir' }"
          :style="item.type === 'dir' ? 'cursor:pointer' : ''"
          @click="item.type === 'dir' ? browse(item.path) : undefined"
        >
          <Checkbox
            v-if="item.type !== 'dir'"
            :model-value="isFileSelected(item.path)"
            @change="toggleFile(item.path)"
          />
          <span v-else style="width:20px;flex-shrink:0" />
          <span style="min-width:140px;font-weight:500;flex-shrink:0">{{ item.name }}</span>
          <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;color:var(--text-dim)">{{ item.path }}</span>
          <span style="min-width:80px;font-size:12px;color:var(--text-dim);flex-shrink:0">{{ item._size }}</span>
          <span style="min-width:60px;flex-shrink:0">
            <Tag :value="item.type" :severity="item.type==='pdf'?'success':'info'" />
          </span>
        </div>
      </div>
    </template>
  </DataView>
  <Paginator :rows="rows" :totalRecords="files.length" @page="onPage" class="mt-2" />
  <LogBar />
</template>

<style scoped>
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.fi { padding: 9px 13px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); font-size: 13px; outline: none; transition: border-color var(--transition); flex: 1; min-width: 200px; }

.breadcrumb { display: flex; align-items: center; gap: 4px; font-size: 13px; flex-wrap: wrap; }
.crumb { color: var(--primary); cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: background 0.15s; }
.crumb:hover { background: var(--primary-bg); }
.crumb.active { color: var(--text-heading); font-weight: 600; cursor: default; }
.crumb.active:hover { background: none; }
.crumb-sep { color: var(--text-dim); font-size: 11px; user-select: none; }
.fi:focus { border-color: var(--primary); box-shadow: var(--focus-ring); }
.dir-row:hover { background: var(--selected); }
.clean-msg { font-size: 12px; color: var(--success); margin-top: 6px; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin-top: 6px; }
.stats-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.op-bar { display: flex; align-items: center; gap: 8px; }
.selected-count { font-size: 12px; color: var(--primary); font-weight: 500; }
.enqueue-msg { font-size: 12px; color: var(--success); }
.select-all-row { display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--surface-raised); border-bottom: 1px solid var(--border); }
.select-all-label { font-size: 12px; color: var(--text-secondary); cursor: pointer; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
</style>
