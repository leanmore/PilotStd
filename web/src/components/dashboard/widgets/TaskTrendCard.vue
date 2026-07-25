<script setup lang="ts">
defineOptions({ name: 'TaskTrendCard' })
import { ref, computed, onMounted } from 'vue'
import { getStats } from '@/api'

const stats = ref({ current: 0, expired: 0, pending: 0, upcoming: 0 })
const total = computed(() => stats.value.current + stats.value.expired + stats.value.pending + stats.value.upcoming)

/* semantic color — consistent across all themes */
const statusList = computed(() => [
  { label: '现行', value: stats.value.current, color: '#22c55e' },
  { label: '废止', value: stats.value.expired, color: '#ef4444' },
  { label: '待确认', value: stats.value.pending, color: '#f59e0b' },
  { label: '即将实施', value: stats.value.upcoming, color: '#3b82f6' },
])

onMounted(async () => {
  try { stats.value = await getStats() } catch { /* ignore */ }
})
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-chart-bar" /></div>
        <div>
          <div class="header-title">标准库构成</div>
          <div class="header-sub">{{ total }} 条标准</div>
        </div>
      </div>
    </div>

    <div v-if="total" class="number-list">
      <div v-for="s in statusList" :key="s.label" class="list-item">
        <span class="item-label" :style="{ color: s.color }">{{ s.label }}</span>
        <span class="item-value">{{ s.value }}</span>
      </div>
    </div>
    <div v-else class="empty-state">
      <p class="empty-text">暂无标准数据</p>
      <p class="empty-hint">导入文件后自动统计</p>
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
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(99,102,241,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--primary); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
.header-sub { font-size: 10px; color: var(--text-dim); }

.number-list { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 10px; }
.list-item { display: flex; justify-content: space-between; align-items: center; font-size: 13px; padding: 4px 0; border-bottom: 1px dashed var(--border-light); }
.list-item:last-child { border-bottom: none; }
.item-label { font-weight: 600; }
.item-value { font-family: var(--mono); font-weight: 700; font-size: 14px; color: var(--text-heading); }

.empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; }
.empty-text { font-size: 13px; color: var(--text-dim); }
.empty-hint { font-size: 11px; color: var(--border); }
</style>
