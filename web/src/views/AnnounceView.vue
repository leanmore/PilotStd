<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getAnnounceResults, postAnnounceCheck } from '@/api'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
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

const page = ref(0)
const rows = ref(25)

const paginatedResults = computed(() => {
  const start = page.value * rows.value
  return results.value.slice(start, start + rows.value)
})

function onPage(e: any) {
  page.value = e.page
}
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
  <template v-if="results.length">
    <DataView :value="paginatedResults" size="small" class="mt-3">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.std_code" class="p-2 border-bottom">
          <div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-light)">
            <strong style="min-width:140px;flex-shrink:0">{{ item.std_code }}</strong>
            <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ item.std_name }}</span>
            <span v-if="item.replaces_code" style="min-width:100px;font-size:12px;color:var(--text-dim);flex-shrink:0">代替: {{ item.replaces_code }}</span>
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
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
</style>
