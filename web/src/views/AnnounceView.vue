<script setup lang="ts">
defineOptions({ name: 'AnnounceView' })
import { ref, onMounted, computed, watch, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { getAnnounceResults, postAnnounceCheck } from '@/api'
import http from '@/api/http'
import { getItem, setItem } from '@/lib/storage'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import AppCalendar from '@/components/AppCalendar.vue'
import UnifiedFilterBar from '@/components/UnifiedFilterBar.vue'
import LogBar from '@/components/LogBar.vue'

const router = useRouter()

// 起始日期默认今天
function defaultSince(): Date {
  const saved = getItem('announce_since')
  return saved ? new Date(saved) : new Date()
}

const activeTab = ref<'gb'|'hb'|'db'>(getItem('announce_tab') as any || 'gb')
watch(activeTab, (v) => { setItem('announce_tab', v); load() })
const results = ref<any[]>([])

// 各适配器抓取开关（默认全部开启，持久化到 localStorage）
const adapterEnabled = reactive({
  gb: getItem('announce_gb_enabled') !== 'false',
  hb: getItem('announce_hb_enabled') !== 'false',
  db: getItem('announce_db_enabled') !== 'false',
})
watch(adapterEnabled, (val) => {
  setItem('announce_gb_enabled', String(val.gb))
  setItem('announce_hb_enabled', String(val.hb))
  setItem('announce_db_enabled', String(val.db))
}, { deep: true })

// 新版统计数据
interface AnnounceStats {
  total: { all: number; gb: number; hb: number; db: number }
  matched: number
  new: { all: number; gb: number; hb: number; db: number }
}
const statsData = ref<AnnounceStats | null>(null)

async function loadStats() {
  try { statsData.value = await http.get('/announce/stats').then(r => r.data) } catch { /* ignore */ }
}
const loading = ref(false)
const sinceDate = ref<Date>(defaultSince())
watch(sinceDate, (v) => {
  setItem('announce_since', v.toISOString())
  const ds = `${v.getFullYear()}-${String(v.getMonth()+1).padStart(2,'0')}-${String(v.getDate()).padStart(2,'0')}`
  http.post('/user-preference', null, { params: { key: 'announce_since_date', value: ds } }).catch(() => {})
})
const error = ref('')

async function load() {
  try {
    const sourceSite = `announcement_${activeTab.value}`
    const fromDate = sinceDate.value
      ? `${sinceDate.value.getFullYear()}-${String(sinceDate.value.getMonth() + 1).padStart(2, '0')}-${String(sinceDate.value.getDate()).padStart(2, '0')}`
      : ''
    const data = await getAnnounceResults(sourceSite, fromDate)
    results.value = data.results || []
    loadStats()
  } catch {}
}

async function check() {
  loading.value = true; error.value = ''
  try {
    const sinceStr = sinceDate.value
      ? `${sinceDate.value.getFullYear()}-${String(sinceDate.value.getMonth()+1).padStart(2,'0')}-${String(sinceDate.value.getDate()).padStart(2,'0')}`
      : undefined
    // 收集已启用的适配器类型
    const enabledTypes = (Object.keys(adapterEnabled) as ('gb'|'hb'|'db')[])
      .filter(k => adapterEnabled[k])
    if (enabledTypes.length === 0) { error.value = '请至少开启一个公告类型'; return }
    const typesStr = enabledTypes.join(',')
    const r = await postAnnounceCheck(sinceStr, typesStr)
    if (!r.ok) { error.value = '公告检查失败'; return }
    await load()
  } catch (e: any) { error.value = '公告检查失败，请查看后台日志' }
  finally { loading.value = false }
}

onMounted(load)

const page = ref(Number(getItem('announce_page')) || 0)
const rows = ref(Number(getItem('announce_rows')) || 25)

const paginatedResults = computed(() => {
  const start = page.value * rows.value
  return results.value.slice(start, start + rows.value)
})

function onPage(e: any) {
  page.value = e.page
  setItem('announce_page', String(e.page))
}
</script>

<template>
  <h1>公告</h1>
  <div class="header">
    <UnifiedFilterBar
      v-model:current-tab="activeTab"
      :fetch-enabled="adapterEnabled"
      @update:fetch-enabled="(key, val) => { const k = key as 'gb'|'hb'|'db'; adapterEnabled[k] = val }"
    />
    <AppCalendar v-model="sinceDate" dateFormat="yy-mm-dd" showIcon style="width:160px" />
    <Button label="立即抓取" icon="pi pi-refresh" :loading="loading" @click="check" size="small" />
  </div>
  <p v-if="error" class="err-msg">{{ error }}</p>
  <!-- 统计数据 -->
  <div v-if="statsData" class="stats-grid mt-2">
    <div class="stat-card"><div class="stat-num">{{ statsData.total.all }}</div><div class="stat-label">标准总数</div><div class="stat-sub">国标 {{ statsData.total.gb }} · 行标 {{ statsData.total.hb }} · 地标 {{ statsData.total.db }}</div></div>
    <div class="stat-card"><div class="stat-num">{{ statsData.matched }}</div><div class="stat-label">已匹配</div></div>
    <div class="stat-card"><div class="stat-num">{{ statsData.new.all }}</div><div class="stat-label">今日新增</div><div class="stat-sub">国标 {{ statsData.new.gb }} · 行标 {{ statsData.new.hb }} · 地标 {{ statsData.new.db }}</div></div>
  </div>
  <template v-if="results.length">
    <DataView :value="paginatedResults" size="small" class="mt-3">
      <template #list="slotProps">
        <div v-for="(item, idx) in slotProps.items" :key="item.announce_no || idx" class="p-2 border-bottom announce-row" @click="router.push('/announce/' + encodeURIComponent(item.announce_no))">
          <div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-light)">
            <strong style="min-width:140px;flex-shrink:0">{{ item.announce_no }}</strong>
            <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ item.announcement_title }}</span>
            <span v-if="item.standard_count" style="min-width:60px;font-size:12px;color:var(--text-dim);flex-shrink:0">({{ item.standard_count }}项)</span>
            <span style="min-width:90px;font-size:12px;color:var(--text-dim);flex-shrink:0">{{ item.publish_date }}</span>
          </div>
        </div>
      </template>
    </DataView>
    <Paginator :rows="rows" :totalRecords="results.length" @page="onPage" class="mt-2" />
  </template>
  <LogBar />
</template>

<style scoped>
.header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin: 4px 0; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; text-align: center; }
.stat-num { font-size: 28px; font-weight: 700; color: var(--primary); font-family: var(--mono); }
.stat-label { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
.stat-sub { font-size: 11px; color: var(--text-dim); margin-top: 6px; line-height: 1.5; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
.announce-row { cursor: pointer; transition: background 0.15s; }
.announce-row:hover { background: var(--surface-hover, #f3f4f6); }
</style>
