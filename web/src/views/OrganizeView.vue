<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getFiles, postCleanEmpty } from '@/api'
import Button from 'primevue/button'
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
    const data = await getFiles(p)
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

onMounted(() => browse())

const page = ref(0)
const rows = ref(30)

const paginatedFiles = computed(() => {
  const start = page.value * rows.value
  return files.value.slice(start, start + rows.value)
})

function onPage(e: any) {
  page.value = e.page
}

// 面包屑：当前路径拆成逐段可点击的导航
import { computed } from 'vue'
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

  <!-- 统计 -->
  <div class="stats-row mt-2">
    <Tag severity="info" :value="files.length + ' 个文件'" />
    <Tag severity="success" :value="files.filter(f=>f.type==='pdf').length + ' PDF'" />
    <Tag severity="warn" :value="files.filter(f=>f.type!=='pdf').length + ' 其他'" />
  </div>

  <!-- 文件列表 -->
  <DataView :value="paginatedFiles" size="small" class="mt-2">
    <template #list="slotProps">
      <div v-for="item in slotProps.items" :key="item.path" class="p-2 border-bottom">
        <div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-light);align-items:center">
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
.clean-msg { font-size: 12px; color: var(--success); margin-top: 6px; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin-top: 6px; }
.stats-row { display: flex; gap: 8px; flex-wrap: wrap; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
</style>
