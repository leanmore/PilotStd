<script setup lang="ts">
defineOptions({ name: 'StatsCard' })
// StatsCard.vue — 统计数字卡 Widget（多值展示：现行/废止/即将实施/待确认）
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getStats } from '@/api'

const { t } = useI18n()

const stats = ref({ current: 0, expired: 0, pending: 0, upcoming: 0 })
const loading = ref(true)
const error = ref(false)

const items = [
  { key: 'current', label: t('home.current'), icon: 'pi pi-verified', color: '#10b981' },
  { key: 'expired', label: t('home.expired'), icon: 'pi pi-times-circle', color: '#ef4444' },
  { key: 'pending', label: t('home.pending'), icon: 'pi pi-hourglass', color: '#f59e0b' },
  { key: 'upcoming', label: t('home.upcoming'), icon: 'pi pi-calendar-plus', color: '#3b82f6' },
]

onMounted(async () => {
  try {
    const data = await getStats()
    stats.value = data
    error.value = false
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="stats-multi-widget">
    <template v-if="loading">
      <div class="stats-grid">
        <div v-for="item in items" :key="item.key" class="stat-item">
          <div class="skeleton-line skeleton-num" />
          <div class="skeleton-line skeleton-label" />
        </div>
      </div>
    </template>
    <template v-else>
      <div class="stats-grid">
        <div v-for="item in items" :key="item.key" class="stat-item">
          <div class="stat-value" :style="{ color: error ? 'var(--text-dim)' : item.color }">
            {{ error ? '—' : stats[item.key as keyof typeof stats] ?? 0 }}
          </div>
          <div class="stat-label">
            <i :class="item.icon" style="font-size:11px;margin-right:3px" />
            {{ item.label }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stats-multi-widget {
  height: 100%;
  display: flex;
  align-items: center;
  padding: 16px 20px;
  box-sizing: border-box;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  width: 100%;
}
.stat-item {
  text-align: center;
  padding: 4px 0;
}
.stat-value {
  font-size: 28px;
  font-weight: 800;
  font-family: var(--mono);
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 2px;
  font-weight: 600;
}
.skeleton-line {
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
  margin: 0 auto;
}
.skeleton-num { height: 28px; width: 50%; margin-bottom: 8px; }
.skeleton-label { height: 12px; width: 60%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
