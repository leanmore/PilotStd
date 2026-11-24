<script setup lang="ts">
defineOptions({ name: 'PendingItemsCard' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()

interface PendingItem { id: number; standard_number: string; standard_name?: string; status?: string; source_site?: string }

const items = ref<PendingItem[]>([])
const total = ref(0)
const loading = ref(true)
// 2026-11-25 修复（D-1）：原实现只有 `finally` 没有 `catch`，接口失败时 items 为空 +
// loading=false → 渲染「全部处理完毕」，把网络/后端故障谎报成"没有待办"。
const error = ref(false)

function load() {
  error.value = false
  loading.value = true
  http.get('/pending', { routeTag: '/' })
    .then((r) => {
      items.value = (r.data.items || []).slice(0, 6)
      total.value = r.data.total ?? r.data.items?.length ?? 0
    })
    .catch(() => { error.value = true })
    .finally(() => { loading.value = false })
}

onMounted(load)
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-clock" /></div>
        <div>
          <div class="header-title">{{ t('dashboard.card.pending') }}</div>
          <div class="header-sub">{{ t('dashboard.pending.total', { n: total }) }}</div>
        </div>
      </div>
    </div>

    <div v-if="error" class="empty">
      <i class="pi pi-exclamation-triangle" style="font-size: var(--font-size-24); color: var(--danger); margin-bottom: var(--space-8);" />
      <span>{{ t('dashboard.common.load_failed') }}</span>
      <AppButton :label="t('common.retry')" size="s" type="ghost" class="retry-link" @click="load" />
    </div>

    <div v-else-if="!items.length && !loading" class="empty">
      <i class="pi pi-check-circle" style="font-size: var(--font-size-24); color: var(--success); margin-bottom: var(--space-8);" />
      <span>{{ t('dashboard.pending.all_done') }}</span>
    </div>

    <div v-else class="list">
      <div v-for="item in items" :key="item.id" class="row">
        <div class="row-tag">{{ item.source_site || 'STD' }}</div>
        <div class="row-info">
          <div class="row-name">{{ item.standard_number }}</div>
          <div class="row-date">{{ item.standard_name || '' }}</div>
        </div>
        <i class="pi pi-chevron-right row-arrow" />
      </div>
      <div v-if="total > 6" class="more">{{ t('dashboard.pending.more', { n: total - 6 }) }}</div>
    </div>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: var(--space-14);
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: var(--space-10);
}
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: var(--space-10); }
.header-icon {
  width: 34px; height: var(--icon-tile-md); border-radius: var(--radius-sm); background: var(--danger-bg);
  display: flex; align-items: center; justify-content: center; color: var(--danger); font-size: var(--font-size-16);
}
.header-title { font-size: var(--font-size-13); font-weight: var(--font-weight-bold); color: var(--text-heading); }
.header-sub { font-size: var(--font-size-10); color: var(--text-dim); }

.list { flex: 1; display: flex; flex-direction: column; gap: var(--space-6); overflow-y: auto; }
.row {
  display: flex; align-items: center; gap: var(--space-10); padding: var(--space-10) var(--space-12);
  background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
  transition: all var(--transition); cursor: pointer;
}
.row:hover { border-color: var(--primary-border); background: var(--primary-bg); }
.row-tag {
  padding: var(--space-2) var(--space-6); border-radius: var(--ds-radius-xs); font-size: var(--font-size-9); font-weight: var(--font-weight-bold); font-family: var(--mono);
  background: var(--warning-bg); color: var(--warning); flex-shrink: 0;
}
.row-info { flex: 1; min-width: 0; }
.row-name { font-size: var(--font-size-12); font-weight: var(--font-weight-semibold); color: var(--text-heading); font-family: var(--mono); display: block; }
.row-date {
  font-size: var(--font-size-11); color: var(--text-dim); margin-top: var(--space-2);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.row-arrow { font-size: var(--font-size-10); color: var(--text-dim); flex-shrink: 0; }
.more { font-size: var(--font-size-11); color: var(--text-dim); text-align: center; padding-top: var(--space-4); }
.empty { color: var(--text-dim); font-size: var(--font-size-12); text-align: center; padding: var(--space-30) 0; flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }
</style>
