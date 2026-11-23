<script setup lang="ts">
defineOptions({ name: 'PendingView' })
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import Tag from 'primevue/tag'
import { getPendingItems, postRequery } from '@/api'
import { severityOfStatusKey } from '@/utils/stdStatus'
import { getItem, setItem } from '@/lib/storage'
import LogBar from '@/components/LogBar.vue'
import { useQueryAdapters } from '@/composables/useQueryAdapters'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppLoading from '@/components/ui/AppLoading.vue'

const { adapters, loading: adaptersLoading, error: adaptersError, ensure, refresh: refreshAdapters } = useQueryAdapters('/pending')
const { t } = useI18n()

const input = ref('')
const results = ref<any[]>([])
const loading = ref(false)
const error = ref('')
const importMsg = ref('')
const selectedSite = ref(getItem('pending_site') || 'ahbz')
watch(selectedSite, (v) => setItem('pending_site', v))

const page = ref(Number(getItem('pending_page')) || 0)
const rows = ref(25)

const paginatedResults = computed(() => {
  const start = page.value * rows.value
  return results.value.slice(start, start + rows.value)
})

function onPage(e: any) {
  page.value = e.page
  setItem('pending_page', String(e.page))
}

async function requery() {
  const numbers = input.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!numbers.length) return
  loading.value = true
  try {
    const r = await postRequery(numbers, selectedSite.value)
    results.value = (r.results || []).map((x: any) => ({ ...x, _site: selectedSite.value }))
    results.value = (r.results || []).map((x: any) => ({ ...x }))
  } catch (e: any) { error.value = t('pending.requery_failed') }
  finally { loading.value = false }
}

// 从服务端 pending_lookup 表导入待确认清单（替代 localStorage）
async function loadPending() {
  importMsg.value = ''
  try {
    const r = await getPendingItems()
    input.value = (r.items || []).map((x: any) => x.standard_number || '').filter(Boolean).join('\n')
    importMsg.value = r.items.length ? t('pending.importResult', { n: r.items.length }) : t('pending.importEmpty')
  } catch { importMsg.value = t('pending.importFailed') }
}
// 只比较后端给的英文键（status_key）；兜底色沿用改造前的 info（#32-C / R14-4c）
function severity(key: string | undefined) {
  return severityOfStatusKey(key, 'info')
}

onMounted(() => { ensure() })
</script>

<template>
  <h1>{{ t('pending.title') }}</h1>
  <p class="hint">{{ t('pending.hint') }}</p>

  <div class="btn-row mb-2">
<AppButton
      :label="t('pending.import_btn')"
      icon="pi pi-list"
      @click="loadPending"
      size="s"
      type="secondary"
    />
    <span v-if="importMsg" class="import-msg">{{ importMsg }}</span>
  </div>

  <div class="mt-2" style="display:flex;gap:var(--space-12);align-items:flex-start">
    <div style="flex:1">
      <AppInput v-model="input" type="textarea" :rows="6" :placeholder="t('pending.input_placeholder')" />
    </div>
  </div>

  <!-- 站点选择 —— 动态加载，带 loading/error/refresh -->
  <div class="card mt-2">
    <div class="card-header">{{ t('pending.select_sites') }}</div>

    <div v-if="adaptersLoading" class="py-3">
      <AppLoading variant="inline" size="s" :label="t('pending.sites_loading')" />
    </div>

    <div v-else-if="adaptersError" class="py-2">
      <p class="err-msg">{{ adaptersError }}</p>
<AppButton
        :label="t('pending.refresh')"
        icon="pi pi-refresh"
        @click="refreshAdapters"
        size="s"
        type="secondary"
      />
    </div>

    <div v-else class="site-grid">
      <div v-for="a in adapters" :key="a.name" class="site-card"
           :class="{ active: selectedSite === a.name }"
           @click="selectedSite = a.name">
        <div class="site-head">
          <span class="site-name">{{ a.display_name }}</span>
          <Tag :value="a.name" severity="info" />
        </div>
      </div>
    </div>
<AppButton
      :label="t('pending.requery')"
      icon="pi pi-search"
      :loading="loading"
      :disabled="adaptersLoading || !!adaptersError"
      @click="requery"
      class="mt-2"
      size="s"
      type="secondary"
    />
  </div>
  <p v-if="error" class="err-msg">{{ error }}</p>

  <template v-if="results.length">
    <DataView :value="paginatedResults" size="small" class="mt-3">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.standard_number" class="p-2 border-bottom">
          <div class="flex justify-content-between align-items-center" style="display:flex;gap:var(--space-12);padding:var(--space-6) 0;border-bottom:1px solid var(--border-light)">
            <div style="flex:1;min-width:0">
              <div><strong>{{ item.standard_number }}</strong></div>
              <div class="text-dim" style="font-size:var(--font-size-13);color:var(--text-dim)">{{ item.standard_name }}</div>
            </div>
            <div class="flex" style="display:flex;gap:var(--space-6);flex-wrap:wrap;align-items:center">
              <Tag :value="item.status" :severity="severity(item.status_key)" />
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
.btn-row { display: flex; align-items: center; gap: var(--space-12); }
.import-msg { font-size: var(--font-size-12); color: var(--accent, #10b981); }
.err-msg { color: var(--danger, #e74c3c); font-size: var(--font-size-12); margin-top: var(--space-6); }

/* 站点卡片网格 —— 与设置页站点管理一致 */
.site-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--space-10); }
.site-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--space-14); cursor: pointer; transition: all 0.15s; }
.site-card:hover { border-color: var(--primary-border); box-shadow: var(--shadow-sm); }
.site-card.active { border-color: var(--primary); background: var(--primary-bg); }
.site-head { display: flex; align-items: center; gap: var(--space-8); margin-bottom: var(--space-6); }
.site-name { font-size: var(--font-size-13); font-weight: var(--font-weight-semibold); color: var(--text-heading); }
.site-desc { font-size: var(--font-size-12); color: var(--text-dim); }
.mt-2 { margin-top: var(--space-12); }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
.text-dim { color: var(--text-dim, #6b7280); }
</style>
