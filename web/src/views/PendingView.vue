<script setup lang="ts">
import { ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'
import { getPendingItems, postRequery } from '@/api'
import LogBar from '@/components/LogBar.vue'

const input = ref('')
const results = ref<any[]>([])
const loading = ref(false)
const error = ref('')
const importMsg = ref('')
const selectedSite = ref('ahbz')

const sites = [
  { name: 'ahbz', label: '安徽标准平台', desc: '免鉴权，覆盖国标/行标/地标/国际/团体' },
  { name: 'njbz365', label: '南京标准网', desc: '覆盖国内外标准' },
  { name: 'std_gov', label: '国家标准公开', desc: 'GB/GB/T 国标' },
  { name: 'hbba', label: '行业标准平台', desc: 'SH/NB/HG/JB 等行标' },
  { name: 'dbba', label: '地方标准平台', desc: 'DB 地方标准' },
  { name: 'iso_gov', label: '国际标准平台', desc: 'ISO/IEC 国际标准' },
  { name: 'csres', label: '工标网', desc: '国标/行标兜底' },
]

async function requery() {
  const numbers = input.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!numbers.length) return
  loading.value = true
  try {
    const r = await postRequery(numbers, selectedSite.value)
    results.value = (r.results || []).map((x: any) => ({ ...x, _site: selectedSite.value }))
    results.value = (r.results || []).map((x: any) => ({ ...x }))
  } catch (e: any) { error.value = '重新查询失败，请查看日志' }
  finally { loading.value = false }
}

// 从服务端 pending_lookup 表导入待确认清单（替代 localStorage）
async function loadPending() {
  importMsg.value = ''
  try {
    const r = await getPendingItems()
    input.value = (r.items || []).map((x: any) => x.standard_number || '').filter(Boolean).join('\n')
    importMsg.value = r.items.length ? `已导入 ${r.items.length} 条待确认标准` : '暂无待确认标准'
  } catch { importMsg.value = '导入失败' }
}
function severity(s: string) {
  if (s === '现行' || s === 'Active') return 'success'
  if (s === '废止' || s === 'Withdrawn') return 'danger'
  if (s === '待确认') return 'warn'
  return 'info'
}
</script>

<template>
  <h1>待确认</h1>
  <p class="hint">对首次查询中匹配度低或不确定的标准，手工导入后指定站点重新查询验证。</p>

  <div class="btn-row mb-2">
    <Button label="导入待确认清单" icon="pi pi-list" size="small" @click="loadPending" />
    <span v-if="importMsg" class="import-msg">{{ importMsg }}</span>
  </div>

  <div class="mt-2" style="display:flex;gap:12px;align-items:flex-start">
    <div style="flex:1">
      <Textarea v-model="input" rows="6" placeholder="输入标准号，一行一个&#10;或从查询结果中粘贴" />
    </div>
  </div>

  <!-- 站点选择 —— 卡片网格，参考设置页样式 -->
  <div class="card mt-2">
    <div class="card-header">选择查询站点</div>
    <div class="site-grid">
      <div v-for="s in sites" :key="s.name" class="site-card" :class="{ active: selectedSite === s.name }" @click="selectedSite = s.name">
        <div class="site-head">
          <span class="site-name">{{ s.label }}</span>
          <Tag :value="s.name" severity="info" />
        </div>
        <div class="site-desc">{{ s.desc }}</div>
      </div>
    </div>
    <Button label="重新查询" icon="pi pi-search" :loading="loading" @click="requery" size="small" class="mt-2" />
  </div>
  <p v-if="error" class="err-msg">{{ error }}</p>

  <DataTable v-if="results.length" :value="results" paginator :rows="25" stripedRows size="small" class="mt-3">
    <Column field="standard_number" header="标准号" />
    <Column field="standard_name" header="名称" />
    <Column field="status" header="状态">
      <template #body="{ data }"><Tag :value="data.status" :severity="severity(data.status)" /></template>
    </Column>
    <Column field="source_site" header="来源" />
    <Column field="match_status" header="匹配" />
    <Column field="_site" header="查询站点">
      <template #body="{ data }"><Tag :value="data._site" severity="info" /></template>
    </Column>
  </DataTable>
  <LogBar />
</template>

<style scoped>
.btn-row { display: flex; align-items: center; gap: 12px; }
.import-msg { font-size: 12px; color: var(--accent, #10b981); }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin-top: 6px; }

/* 站点卡片网格 —— 与设置页站点管理一致 */
.site-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.site-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; cursor: pointer; transition: all 0.15s; }
.site-card:hover { border-color: var(--primary-border); box-shadow: var(--shadow-sm); }
.site-card.active { border-color: var(--primary); background: var(--primary-bg); }
.site-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.site-name { font-size: 13px; font-weight: 600; color: var(--text-heading); }
.site-desc { font-size: 12px; color: var(--text-dim); }
.mt-2 { margin-top: 12px; }
</style>
