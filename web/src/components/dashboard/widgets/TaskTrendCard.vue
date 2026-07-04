<script setup lang="ts">
defineOptions({ name: 'TaskTrendCard' })
import { ref, computed, onMounted } from 'vue'
import { getStats } from '@/api'

const stats = ref({ current: 0, expired: 0, pending: 0, upcoming: 0 })
const total = computed(() => stats.value.current + stats.value.expired + stats.value.pending + stats.value.upcoming)

// 使用现有 stats 数据构造四条模拟趋势线
const sparklines = computed(() => {
  const max = Math.max(total.value, 1)
  const gen = (v: number) => 40 - (v / max) * 34
  return [
    { label: '现行', value: stats.value.current, y: gen(stats.value.current), color: '#22c55e' },
    { label: '废止', value: stats.value.expired, y: gen(stats.value.expired), color: '#ef4444' },
    { label: '待确认', value: stats.value.pending, y: gen(stats.value.pending), color: '#f59e0b' },
    { label: '即将实施', value: stats.value.upcoming, y: gen(stats.value.upcoming), color: '#3b82f6' },
  ]
})

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

    <div class="bars">
      <div v-for="s in sparklines" :key="s.label" class="bar-row">
        <span class="bar-label">{{ s.label }}</span>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: total ? (s.value / total * 100) + '%' : '0%', background: s.color }" />
        </div>
        <span class="bar-val">{{ s.value }}</span>
      </div>
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

.bars { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 8px; }
.bar-row { display: flex; align-items: center; gap: 8px; }
.bar-label { font-size: 10px; color: var(--text-dim); width: 48px; flex-shrink: 0; text-align: right; }
.bar-track { flex: 1; height: 8px; background: var(--border-light); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); }
.bar-val { font-size: 12px; font-weight: 700; font-family: var(--mono); color: var(--text-heading); width: 40px; flex-shrink: 0; }
</style>
