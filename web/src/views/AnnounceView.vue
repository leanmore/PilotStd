<script setup lang="ts">
defineOptions({ name: 'AnnounceView' })
import { ref, onMounted, computed, watch, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getAnnounceResults, getAnnounceFetchFailures, postAnnounceCheck } from '@/api'
import http from '@/api/http'
import { usePreferencesStore } from '@/stores/preferences'
import { getItem, setItem } from '@/lib/storage'
import { SOURCE_TO_URL } from '@/constants/sourceMapping'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import { ANNOUNCE_PAGE_SIZES, resolveRows } from '@/utils/pagination'
import AppCalendar from '@/components/AppCalendar.vue'
import UnifiedFilterBar from '@/components/UnifiedFilterBar.vue'
import LogBar from '@/components/LogBar.vue'

const router = useRouter()
const { t } = useI18n()

// 起始日期 = 「抓取起点（含当日）」，不是列表过滤条件。
// 后端 `pilotstd/announcement/base.py::_fetch_list` 从最新公告往前分页，遇到
// 早于起点的记录即停止 ⇒ 起点越晚，抓到的历史越少。默认不能取「今天」：
// 当天没有新公告时抓取数恒为 0，且会漏掉前几天晚发布/漏抓的公告。
// 默认取最近 7 天，与后端 `announcement.lookback_days` 默认值一致；清空 = 不限起点（全量历史补抓）。
const SINCE_DEFAULT_DAYS = 7

function defaultSince(): Date | null {
  const saved = getItem('announce_since')
  if (saved) {
    const d = new Date(saved)
    if (!Number.isNaN(d.getTime())) return d
  }
  const d = new Date()
  d.setDate(d.getDate() - SINCE_DEFAULT_DAYS)
  return d
}

// YYYY-MM-DD（本地时区），空值返回空串（后端约定空串 = 不限起点）
function formatDate(d: Date | null): string {
  if (!d) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
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

// P1-03：抓取失败历史（读侧）。失败通知已有，但历史/是否恢复此前没有出口。
const fetchFailures = ref<{ total: number; unresolved: number; items: any[] } | null>(null)

async function loadFailures() {
  try {
    fetchFailures.value = await getAnnounceFetchFailures(5, false)
  } catch {
    fetchFailures.value = null
  }
}

async function loadStats() {
  try { statsData.value = (await http.get('/announce/stats', { routeTag: '/announce' })).data } catch { /* ignore */ }
}
const loading = ref(false)
const sinceDate = ref<Date | null>(defaultSince())
watch(sinceDate, (v) => {
  setItem('announce_since', v ? v.toISOString() : '')
  const ds = formatDate(v)
  usePreferencesStore().set('announce_since_date', ds).catch((e) => console.warn('保存抓取起点失败，回落到默认日期', e)) // i18n-allow: 开发者日志：偏好保存失败不影响列表
})
const error = ref('')

async function load() {
  error.value = ''
  try {
    const sourceSite = `announcement_${activeTab.value}`
    // 日期是“抓取起点”，不是列表展示日期：列表不按它过滤，只按来源 Tab 展示
    // 列表走服务端分页（后端原固定 LIMIT 100，公告多的来源会看不到历史）
    const data = await getAnnounceResults(sourceSite, '', '/announce', page.value + 1, rows.value)
    results.value = data.results || []
    totalRecords.value = data.total ?? results.value.length
    loadStats()
    loadFailures()
  } catch {
    error.value = t('announce.view.load_failed')
  }
}

async function check() {
  loading.value = true; error.value = ''
  try {
    // 起点为空 ⇒ 不带 since_date ⇒ 后端不限起点（全量历史补抓）
    const sinceStr = formatDate(sinceDate.value) || undefined
    // 收集已启用的适配器类型
    const enabledTypes = (Object.keys(adapterEnabled) as ('gb'|'hb'|'db')[])
      .filter(k => adapterEnabled[k])
    if (enabledTypes.length === 0) { error.value = t('announce.view.check_no_type'); return }
    const typesStr = enabledTypes.join(',')
    const r = await postAnnounceCheck(sinceStr, typesStr)
    if (!r.ok) { error.value = t('announce.view.check_failed'); return }
    await load()
  } catch (e: any) { error.value = t('announce.view.check_failed_detail') }
  finally { loading.value = false }
}

onMounted(load)

const page = ref(Number(getItem('announce_page')) || 0)
const rows = ref(Number(getItem('announce_rows')) || 25)
// 服务端分页：total 来自接口，列表只放当前页
const totalRecords = ref(0)

const paginatedResults = computed(() => results.value)

function onPage(e: any) {
  page.value = e.page
  setItem('announce_page', String(e.page))
  const next = resolveRows(e.rows, rows.value, ANNOUNCE_PAGE_SIZES)
  if (next !== rows.value) {
    rows.value = next
    page.value = 0
    setItem('announce_rows', String(next))
  }
  // 服务端分页：翻页/改每页条数都要重新取数
  load()
}
</script>

<template>
  <h1>{{ t('announce.view.title') }}</h1>
  <div class="header">
    <UnifiedFilterBar
      v-model:current-tab="activeTab"
      :fetch-enabled="adapterEnabled"
      @update:fetch-enabled="(key, val) => { const k = key as 'gb'|'hb'|'db'; adapterEnabled[k] = val }"
    />
    <AppCalendar v-model="sinceDate" dateFormat="yy-mm-dd" showIcon showClear :placeholder="t('announce.view.since_placeholder')" style="width:160px" />
    <i
      class="pi pi-question-circle since-hint-icon"
      v-tooltip.top="t('announce.view.since_hint')"
      :aria-label="t('announce.view.since_hint')"
      role="img"
      tabindex="0"
    />
    <Button :label="t('announce.view.refresh_list')" icon="pi pi-sync" severity="secondary" outlined size="small" @click="check" />
    <Button :label="t('announce.view.fetch_now')" icon="pi pi-cloud-download" :loading="loading" @click="check" size="small" />
  </div>
  <p v-if="error" class="err-msg">{{ error }}</p>
  <!-- 统计数据 -->
  <div v-if="statsData" class="stats-grid mt-2">
    <div class="stat-card"><div class="stat-num">{{ statsData.total.all }}</div><div class="stat-label">{{ t('announce.view.stat.total') }}</div><div class="stat-sub">{{ t('announce.view.stat.breakdown', { gb: statsData.total.gb, hb: statsData.total.hb, db: statsData.total.db }) }}</div></div>
    <div class="stat-card"><div class="stat-num">{{ statsData.matched }}</div><div class="stat-label">{{ t('announce.view.stat.matched') }}</div></div>
    <div class="stat-card"><div class="stat-num">{{ statsData.new.all }}</div><div class="stat-label">{{ t('announce.view.stat.today_new') }}</div><div class="stat-sub">{{ t('announce.view.stat.breakdown', { gb: statsData.new.gb, hb: statsData.new.hb, db: statsData.new.db }) }}</div></div>
  </div>
  <div v-if="fetchFailures && fetchFailures.total > 0" class="fail-panel mt-2">
    <div class="fail-head">{{ t('announce.view.fetch_failures', { n: fetchFailures.unresolved, total: fetchFailures.total }) }}</div>
    <ul class="fail-list">
      <li v-for="f in fetchFailures.items.slice(0, 5)" :key="f.id">
        <span class="fail-site">{{ f.source_site }}</span>
        <span class="fail-msg">{{ f.error_message }}</span>
        <span class="fail-time">{{ f.created_at }}</span>
      </li>
    </ul>
  </div>
  <template v-if="results.length">
    <DataView :value="paginatedResults" size="small" class="mt-3">
      <template #list="slotProps">
        <div v-for="(item, idx) in slotProps.items" :key="item.announce_no || idx" class="p-2 border-bottom announce-row" @click="router.push('/announce/' + (SOURCE_TO_URL[item.source_site] || 'unknown') + '/' + encodeURIComponent(item.announce_no))">
          <div style="display:flex;gap:var(--space-12);padding:var(--space-6) 0;border-bottom:1px solid var(--border-light)">
            <!-- fix(a11y): 公告号/标题强制 --text-heading——--text-bright 在绿色主题实测仅 4.46:1 未达 AA，--text-heading 四主题 ≥8:1；同时阻断 Aura 亮色 token(#334155) 继承，深色主题对比度 1.8:1→≥8:1；日期/数量由 --text-dim 加深为 --text，绿色主题 2.3:1→≈6.3:1 -->
            <strong style="min-width:140px;flex-shrink:0;color:var(--text-heading)">{{ item.announce_no }}</strong>
            <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-heading)">{{ item.announcement_title }}</span>
            <span v-if="item.standard_count" style="min-width:60px;font-size:var(--font-size-12);color:var(--text);flex-shrink:0">{{ t('announce.view.item_count', { n: item.standard_count }) }}</span>
            <span style="min-width:90px;font-size:var(--font-size-12);color:var(--text);flex-shrink:0">{{ item.publish_date }}</span>
          </div>
        </div>
      </template>
    </DataView>
    <Paginator :rows="rows" :rowsPerPageOptions="ANNOUNCE_PAGE_SIZES" :totalRecords="totalRecords" @page="onPage" class="mt-2" />
    <LogBar class="mt-3" />
  </template>
  <div v-else class="empty-state mt-4">
    <p style="color: var(--text-dim); text-align: center; padding: var(--space-40) 0;">
      {{ t('announce.view.empty_hint') }}
    </p>
  </div>
</template>

<style scoped>
.header { display: flex; align-items: center; gap: var(--space-12); flex-wrap: wrap; }
.err-msg { color: var(--danger, #e74c3c); font-size: var(--font-size-12); margin: var(--space-4) 0; }
/* 起始日期说明改为图标 + Tooltip：颜色/字号/间距全部取 design-tokens.css，不写字面量 */
.since-hint-icon {
  font-size: var(--font-size-13);
  color: var(--text-dim);
  cursor: help;
  transition: color 0.15s ease;
}
.since-hint-icon:hover,
.since-hint-icon:focus-visible { color: var(--text); }
.since-hint-icon:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: var(--space-12); }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--space-14) var(--space-16); text-align: center; }
.fail-panel { border: 1px solid var(--danger, #e74c3c); border-radius: var(--radius); padding: var(--space-10) var(--space-14); background: var(--surface); }
.fail-head { color: var(--danger, #e74c3c); font-size: var(--font-size-13); font-weight: var(--font-weight-semibold); }
.fail-list { list-style: none; margin: var(--space-8) 0 0; padding: 0; }
.fail-list li { display: flex; gap: var(--space-10); font-size: var(--font-size-12); color: var(--text); padding: var(--space-4) 0; border-top: 1px solid var(--border-light, #e5e7eb); }
.fail-site { min-width: 90px; color: var(--text-dim); }
.fail-msg { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fail-time { min-width: 130px; color: var(--text-dim); text-align: right; }
/* fix(a11y): 统计数字改用 --text-heading——项目无 --primary-dark 深色变体，--primary-hover 绿色主题实测 3.14:1、--text-bright 4.46:1 均不达标或余量不足；--text-heading 四主题 ≥8:1 */
.stat-num { font-size: var(--font-size-28); font-weight: var(--font-weight-bold); color: var(--text-heading); font-family: var(--mono); }
.stat-label { font-size: var(--font-size-12); color: var(--text-dim); margin-top: var(--space-4); }
.stat-sub { font-size: var(--font-size-11); color: var(--text-dim); margin-top: var(--space-6); line-height: var(--line-height-normal); }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
.announce-row { cursor: pointer; transition: background 0.15s; }
.announce-row:hover { background: var(--selected); }
</style>
