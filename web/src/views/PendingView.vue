<script setup lang="ts">
defineOptions({ name: 'PendingView' })
import { ref, computed } from 'vue'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
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

const page = ref(0)
const rows = ref(25)

const paginatedResults = computed(() => {
  const start = page.value * rows.value
  return results.value.slice(start, start + rows.value)
})

function onPage(e: any) {
  page.value = e.page
}

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

  <template v-if="results.length">
    <DataView :value="paginatedResults" size="small" class="mt-3">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.standard_number" class="p-2 border-bottom">
          <div class="flex justify-content-between align-items-center" style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-light)">
            <div style="flex:1;min-width:0">
              <div><strong>{{ item.standard_number }}</strong></div>
              <div class="text-dim" style="font-size:13px;color:var(--text-dim)">{{ item.standard_name }}</div>
            </div>
            <div class="flex" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
              <Tag :value="item.status" :severity="severity(item.status)" />
              <Tag :value="item._site" severity="info" />
            </div>
          </div>
        </div>
      </template>
    </DataView>
    <Paginator :rows="rows" :totalRecords="results.length" @page="onPage" class="mt-2" />
  </template>
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
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
.text-dim { color: var(--text-dim, #6b7280); }
</style>
