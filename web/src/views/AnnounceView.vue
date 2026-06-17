<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAnnounceResults, postAnnounceCheck } from '@/api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Calendar from 'primevue/calendar'
import LogBar from '@/components/LogBar.vue'

// 起始日期默认往前3个月，与 Windows GUI 公告检查一致
function defaultSince(): Date {
  const d = new Date(); d.setMonth(d.getMonth() - 3); return d
}

const tab = ref<'gb'|'hb'|'db'>(window.localStorage.getItem('announce_tab') as any || 'gb')
const tabs: { key: 'gb'|'hb'|'db', label: string, api: string }[] = [
  { key: 'gb', label: '国家标准公告', api: 'nocGBPage' },
  { key: 'hb', label: '行业标准公告', api: 'nocHBPage' },
  { key: 'db', label: '地方标准公告', api: 'nocDBPage' },
]
const results = ref<any[]>([])
const summary = ref<any>({})
const loading = ref(false)
const lastCheck = ref('')
const sinceDate = ref<Date>(defaultSince())
const error = ref('')

function switchTab(k: 'gb'|'hb'|'db') { tab.value = k; window.localStorage.setItem('announce_tab', k); load() }

async function load() {
  try {
    const data = await getAnnounceResults()
    results.value = (data.results || []).filter((x: any) => (x.type || 'gb') === tab.value)
    summary.value = data.summary || {}
    lastCheck.value = data.last_check || ''
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
</script>

<template>
  <h1>公告</h1>
  <div class="header">
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" :class="{ active: tab === t.key }" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>
    <Calendar v-model="sinceDate" dateFormat="yy-mm-dd" showIcon style="width:160px" />
    <span v-if="lastCheck" class="text-dim">上次: {{ lastCheck }}</span>
    <Button label="立即检查" icon="pi pi-refresh" :loading="loading" @click="check" size="small" />
  </div>
  <p v-if="error" class="err-msg">{{ error }}</p>
  <div v-if="Object.keys(summary).length" class="mt-2" style="display:flex;gap:8px">
    <Tag v-for="(v,k) in summary" :key="k" :value="`${k}: ${v}`" />
  </div>
  <DataTable :value="results" paginator :rows="25" stripedRows size="small" class="mt-3">
    <Column field="std_code" header="标准号" />
    <Column field="std_name" header="名称" />
    <Column field="replaces_code" header="代替" />
    <Column field="publish_date" header="日期" />
  </DataTable>
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
</style>
