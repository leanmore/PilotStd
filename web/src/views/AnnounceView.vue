<script setup lang="ts">
defineOptions({ name: 'AnnounceView' })
import { ref, onMounted, computed, watch } from 'vue'
import { getAnnounceResults, postAnnounceCheck } from '@/api'
import http from '@/api/http'
import { getItem, setItem } from '@/lib/storage'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import Calendar from 'primevue/calendar'
import LogBar from '@/components/LogBar.vue'

// 起始日期默认今天
function defaultSince(): Date {
  const saved = getItem('announce_since')
  return saved ? new Date(saved) : new Date()
}

const tab = ref<'gb'|'hb'|'db'>(getItem('announce_tab') as any || 'gb')
const tabs: { key: 'gb'|'hb'|'db', label: string, api: string }[] = [
  { key: 'gb', label: '国家标准公告', api: 'nocGBPage' },
  { key: 'hb', label: '行业标准公告', api: 'nocHBPage' },
  { key: 'db', label: '地方标准公告', api: 'nocDBPage' },
]
const results = ref<any[]>([])

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
watch(sinceDate, (v) => setItem('announce_since', v.toISOString()))
const error = ref('')

function switchTab(k: 'gb'|'hb'|'db') { tab.value = k; setItem('announce_tab', k); load() }

async function load() {
  try {
    const data = await getAnnounceResults()
    const sourceSite = `announcement_${tab.value}`
    results.value = (data.results || []).filter((x: any) => x.source_site === sourceSite)
    loadStats()
  } catch {}
}

async function check() {
  loading.value = true; error.value = ''
  try {
    const sinceStr = sinceDate.value
      ? `${sinceDate.value.getFullYear()}-${String(sinceDate.value.getMonth()+1).padStart(2,'0')}-${String(sinceDate.value.getDate()).padStart(2,'0')}`
      : undefined
    const r = await postAnnounceCheck(sinceStr)
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
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" :class="{ active: tab === t.key }" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>
    <Calendar v-model="sinceDate" dateFormat="yy-mm-dd" showIcon style="width:160px" />
    <Button label="立即检查" icon="pi pi-refresh" :loading="loading" @click="check" size="small" />
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
        <div v-for="(item, idx) in slotProps.items" :key="item.announce_no || idx" class="p-2 border-bottom">
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
.tabs { display: flex; gap: 0; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow-xs); }
.tabs button { padding: 9px 18px; border: none; background: none; color: var(--text-dim); cursor: pointer; font-size: 13px; font-weight: 500; border-right: 1px solid var(--border); transition: all var(--transition); }
.tabs button:last-child { border-right: none; }
.tabs button:hover { color: var(--text); }
.tabs button.active { background: var(--primary-bg); color: var(--primary); font-weight: 600; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin: 4px 0; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; text-align: center; }
.stat-num { font-size: 28px; font-weight: 700; color: var(--primary); font-family: var(--mono); }
.stat-label { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
.stat-sub { font-size: 11px; color: var(--text-dim); margin-top: 6px; line-height: 1.5; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
</style>
