<script setup lang="ts">
defineOptions({ name: 'PendingItemsCard' })
import { ref, onMounted } from 'vue'
import http from '@/api/http'

interface PendingItem { id: number; standard_number: string; std_name?: string; status?: string; source_site?: string }

const items = ref<PendingItem[]>([])
const total = ref(0)
const loading = ref(true)

onMounted(async () => {
  try {
    const r = await http.get('/pending')
    items.value = (r.data.items || []).slice(0, 6)
    total.value = r.data.total ?? r.data.items?.length ?? 0
  } finally { loading.value = false }
})
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-clock" /></div>
        <div>
          <div class="header-title">待确认标准</div>
          <div class="header-sub">{{ total }} 项待处理</div>
        </div>
      </div>
    </div>

    <div v-if="!items.length && !loading" class="empty">
      <i class="pi pi-check-circle" style="font-size: 24px; color: var(--success); margin-bottom: 8px;" />
      <span>全部处理完毕</span>
    </div>

    <div v-else class="list">
      <div v-for="item in items" :key="item.id" class="row">
        <div class="row-tag">{{ item.source_site || 'STD' }}</div>
        <div class="row-info">
          <div class="row-name">{{ item.standard_number }}</div>
          <div class="row-date">{{ item.std_name || '' }}</div>
        </div>
        <i class="pi pi-chevron-right row-arrow" />
      </div>
      <div v-if="total > 6" class="more">还有 {{ total - 6 }} 项...</div>
    </div>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: 14px;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: 10px;
}
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon {
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(239,68,68,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--danger); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
.header-sub { font-size: 10px; color: var(--text-dim); }

.list { flex: 1; display: flex; flex-direction: column; gap: 6px; overflow-y: auto; }
.row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
  transition: all var(--transition); cursor: pointer;
}
.row:hover { border-color: var(--primary-border); background: var(--primary-bg); }
.row-tag {
  padding: 2px 6px; border-radius: 4px; font-size: 9px; font-weight: 700; font-family: var(--mono);
  background: rgba(245,158,11,0.12); color: var(--warning); flex-shrink: 0;
}
.row-info { flex: 1; min-width: 0; }
.row-name { font-size: 12px; font-weight: 600; color: var(--text-heading); font-family: var(--mono); display: block; }
.row-date {
  font-size: 11px; color: var(--text-dim); margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.row-arrow { font-size: 10px; color: var(--text-dim); flex-shrink: 0; }
.more { font-size: 11px; color: var(--text-dim); text-align: center; padding-top: 4px; }
.empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 30px 0; flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }
</style>
