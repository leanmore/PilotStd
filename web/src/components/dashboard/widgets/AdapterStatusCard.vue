<script setup lang="ts">
defineOptions({ name: 'AdapterStatusCard' })
// AdapterStatusCard.vue — 适配器熔断状态 Widget（从 DashboardView 迁移）
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import Tag from 'primevue/tag'
import Column from 'primevue/column'
import AppTable from '@/components/ui/AppTable.vue'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()

interface AdapterStatus {
  name: string
  status: string
  frozen_until: string | null
  remaining_seconds: number
  freeze_count: number
  fail_streak: number
}

const adapters = ref<AdapterStatus[]>([])
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setInterval> | null = null

async function loadStatus() {
  loading.value = true
  try {
    const r = await http.get('/adapter/status', { routeTag: '/' })
    adapters.value = r.data.adapters
    error.value = ''
  } catch {
    error.value = t('dashboard.adapter.load_failed')
  } finally {
    loading.value = false
  }
}

function tick() {
  let anyFrozen = false
  for (const a of adapters.value) {
    if (a.status === 'frozen' && a.remaining_seconds > 0) {
      a.remaining_seconds--
      anyFrozen = true
    }
  }
  if (!anyFrozen && adapters.value.some(a => a.status === 'frozen')) {
    loadStatus()
  }
}

function statusSeverity(s: string): 'success' | 'danger' | 'info' {
  if (s === 'frozen') return 'danger'
  if (s === 'normal') return 'success'
  return 'info'
}

function statusLabel(s: string): string {
  if (s === 'frozen') return t('dashboard.adapter.frozen')
  if (s === 'normal') return t('dashboard.common.normal')
  if (s === 'error') return t('dashboard.adapter.error')
  console.warn('[AdapterStatusCard] 未映射的适配器状态:', s) // i18n-allow: 开发者日志：未映射的适配器状态
  return s
}

onMounted(() => {
  loadStatus()
  timer = setInterval(tick, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="adapter-widget">
    <div class="widget-header">
      <span>{{ t('dashboard.adapter.title') }}</span>
      <AppButton
        icon="pi pi-refresh"
        :loading="loading"
        @click="loadStatus"
        size="s"
        type="ghost"
      />
    </div>
    <p v-if="error" class="err-msg">{{ error }}</p>
    <AppTable v-if="adapters.length" :value="adapters" dataKey="name" size="small" table-class="adapter-table">
      <Column :header="t('dashboard.adapter.col_adapter')">
        <template #body="{ data }"><strong>{{ data.name.toUpperCase() }}</strong></template>
      </Column>
      <Column :header="t('dashboard.adapter.col_status')">
        <template #body="{ data }">
          <Tag :severity="statusSeverity(data.status)" :value="statusLabel(data.status)" />
        </template>
      </Column>
      <Column :header="t('dashboard.adapter.col_remaining')">
        <template #body="{ data }">{{ data.status === 'frozen' ? `${data.remaining_seconds}s` : '—' }}</template>
      </Column>
      <Column :header="t('dashboard.adapter.col_freeze_count')" field="freeze_count" />
      <Column :header="t('dashboard.adapter.col_fail_streak')" field="fail_streak" />
    </AppTable>
    <p v-else-if="!loading" class="empty">{{ t('dashboard.adapter.empty') }}</p>
  </div>
</template>

<style scoped>
.adapter-widget {
  height: 100%;
  box-sizing: border-box;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  padding: var(--space-20);
  display: flex;
  flex-direction: column;
  transition: all var(--transition);
}
.adapter-widget:hover {
  box-shadow: var(--shadow-md);
}

.widget-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: var(--font-weight-bold);
  color: var(--text-heading);
  font-size: var(--font-size-15);
  margin-bottom: var(--space-16);
  padding-bottom: var(--space-12);
  border-bottom: 2px solid var(--border);
}

/* 仪表盘紧凑表格：本组件刻意不走 AppTable 的常规行高（面板空间有限，用 12/13px 字号 +
   6~10px 内边距 + 表头 2px 下边框），故通过 table-class 把 .adapter-table 挂到内层 table 上，
   再用 :deep() 穿透 —— PrimeVue 渲染的 thead/tbody/th/td 不带本组件的 scope 属性，
   不加 :deep() 这些规则一条都不会生效。 */
.adapter-table :deep(th) {
  font-weight: var(--font-weight-semibold);
  color: var(--text-dim);
  font-size: var(--font-size-11);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--space-8) var(--space-10);
  background: var(--surface-raised);
  border-bottom: 2px solid var(--border);
}
.adapter-table :deep(th:first-child) { border-radius: var(--radius-sm) 0 0 0; }
.adapter-table :deep(th:last-child) { border-radius: 0 var(--radius-sm) 0 0; }
.adapter-table :deep(td) {
  padding: var(--space-10);
  border-bottom: 1px solid var(--border-light);
  color: var(--text);
}
.adapter-table :deep(tbody tr) {
  transition: all var(--transition);
}
.adapter-table :deep(tbody tr:hover) {
  background: var(--selected);
}
.adapter-table :deep(tbody tr:last-child td) { border-bottom: none; }

.empty {
  color: var(--text-dim);
  font-size: var(--font-size-13);
  padding: var(--space-24) 0;
  text-align: center;
}
.err-msg {
  color: var(--danger);
  font-size: var(--font-size-12);
  margin: var(--space-4) 0;
}

/* 响应式 */
@media (max-width: 767px) {
  .adapter-widget { padding: var(--space-16); }
  .adapter-table :deep(th), .adapter-table :deep(td) { padding: var(--space-6) var(--space-8); }
}
</style>
