<script setup lang="ts">
// StatsCard.vue — 统计数字卡 Widget（复用 4 次：现行/废止/待确认/即将实施）
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getStats } from '@/api'

const { t } = useI18n()

const props = defineProps<{
  widget: {
    id: string
    config: Record<string, unknown>
  }
}>()

const statKey = (props.widget.config.statKey as string) || 'current'
const labelMap: Record<string, string> = {
  current: t('home.current'),
  expired: t('home.expired'),
  pending: t('home.pending'),
  upcoming: t('home.upcoming'),
}
const iconMap: Record<string, string> = {
  current: 'pi pi-verified',
  expired: 'pi pi-times-circle',
  pending: 'pi pi-hourglass',
  upcoming: 'pi pi-calendar-plus',
}
const gradientMap: Record<string, string> = {
  current: 'linear-gradient(135deg, #10b981, #34d399)',
  expired: 'linear-gradient(135deg, #ef4444, #f87171)',
  pending: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
  upcoming: 'linear-gradient(135deg, #3b82f6, #60a5fa)',
}

const value = ref<number | null>(null)
const loading = ref(true)
const error = ref(false)

onMounted(async () => {
  try {
    const stats = await getStats()
    value.value = (stats as Record<string, number>)[statKey] ?? 0
    error.value = false
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="stats-card-widget">
    <template v-if="loading">
      <div class="stat-icon-box skeleton-box" />
      <div class="stat-info">
        <div class="skeleton-line skeleton-num" />
        <div class="skeleton-line skeleton-label" />
      </div>
    </template>
    <template v-else>
      <div class="stat-icon-box" :style="{ background: gradientMap[statKey] }">
        <i :class="iconMap[statKey]" />
      </div>
      <div class="stat-info">
        <div class="stat-num" :class="{ 'stat-err': error }">
          {{ error ? '—' : (value ?? '—') }}
        </div>
        <div class="stat-label">{{ labelMap[statKey] }}</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stats-card-widget {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  height: 100%;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition), transform var(--transition);
}
.stats-card-widget:hover {
  box-shadow: var(--shadow);
  transform: translateY(-1px);
}

.stat-icon-box {
  width: 48px;
  height: 48px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-info { flex: 1; min-width: 0; }
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-heading);
  font-family: var(--mono);
  line-height: 1.2;
  letter-spacing: -0.02em;
}
.stat-label {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 2px;
  font-weight: 500;
}
.stat-err { color: var(--danger); }

/* 骨架加载 */
.skeleton-box { background: var(--border-light); }
.skeleton-line {
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.skeleton-num { height: 28px; width: 60%; margin-bottom: 6px; }
.skeleton-label { height: 14px; width: 40%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
