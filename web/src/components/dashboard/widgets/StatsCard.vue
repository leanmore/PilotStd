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
  gap: 18px;
  padding: 24px;
  height: 100%;
  box-sizing: border-box;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
}
.stats-card-widget::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 120px;
  height: 120px;
  background: radial-gradient(circle, var(--primary-bg), transparent 70%);
  opacity: 0.5;
  pointer-events: none;
}
.stats-card-widget:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-3px);
  border-color: var(--primary-border);
}

.stat-icon-box {
  width: 52px;
  height: 52px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 22px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
  position: relative;
  z-index: 1;
  transition: all var(--transition);
}
.stats-card-widget:hover .stat-icon-box {
  transform: scale(1.05) rotate(-3deg);
}

.stat-info { flex: 1; min-width: 0; position: relative; z-index: 1; }
.stat-num {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-heading);
  font-family: var(--mono);
  line-height: 1.1;
  letter-spacing: -0.03em;
}
.stat-label {
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
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
.skeleton-num { height: 32px; width: 60%; margin-bottom: 8px; }
.skeleton-label { height: 14px; width: 40%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 响应式 */
@media (max-width: 767px) {
  .stats-card-widget { padding: 18px; gap: 14px; }
  .stat-icon-box { width: 44px; height: 44px; font-size: 18px; }
  .stat-num { font-size: 26px; }
  .stat-label { font-size: 11px; }
}
</style>
