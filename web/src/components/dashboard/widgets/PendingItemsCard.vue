<script setup lang="ts">
defineOptions({ name: 'PendingItemsCard' })
// PendingItemsCard.vue — 待确认标准列表 Widget
import { ref, onMounted } from 'vue'
import http from '@/api/http'

interface PendingItem {
  id: number
  standard_number: string
  std_name?: string
  status?: string
  source_site?: string
}

const items = ref<PendingItem[]>([])
const total = ref(0)
const loading = ref(true)

onMounted(async () => {
  try {
    const r = await http.get('/pending')
    items.value = (r.data.items || []).slice(0, 5)
    total.value = r.data.total ?? r.data.items?.length ?? 0
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="pending-widget">
    <div class="w-header">
      <span class="w-title">待确认标准</span>
      <span v-if="total > 0" class="w-badge">{{ total }}</span>
    </div>
    <div v-if="loading" class="w-empty">加载中...</div>
    <div v-else-if="items.length === 0" class="w-empty">暂无待确认标准</div>
    <div v-else class="w-list">
      <div v-for="item in items" :key="item.id" class="w-row">
        <code class="w-num">{{ item.standard_number }}</code>
        <span class="w-name">{{ item.std_name || '—' }}</span>
      </div>
      <div v-if="total > 5" class="w-more">还有 {{ total - 5 }} 项...</div>
    </div>
  </div>
</template>

<style scoped>
.pending-widget {
  height: 100%;
  box-sizing: border-box;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}
.w-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.w-title { font-weight: 700; color: var(--text-heading); font-size: 15px; }
.w-badge { background: var(--warning); color: #fff; border-radius: 12px; padding: 2px 10px; font-size: 12px; font-weight: 700; }
.w-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-dim); font-size: 13px; }
.w-list { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.w-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid var(--border-light); font-size: 13px; }
.w-num { font-weight: 600; color: var(--primary); font-size: 12px; }
.w-name { color: var(--text-dim); max-width: 55%; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.w-more { font-size: 11px; color: var(--text-dim); text-align: center; padding-top: 4px; }
</style>
