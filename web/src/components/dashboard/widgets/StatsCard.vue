<script setup lang="ts">
defineOptions({ name: 'StatsCard' })
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getStats } from '@/api'

const { t } = useI18n()

const stats = ref({ current: 0, expired: 0, pending: 0, upcoming: 0 })
const loading = ref(true)
const error = ref(false)

onMounted(async () => {
  try {
    stats.value = await getStats()
    error.value = false
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="mp-stats-root">
    <!-- 骨架加载 -->
    <template v-if="loading">
      <div class="mp-skeleton-main" />
      <div class="mp-skeleton-sub" v-for="i in 3" :key="i" />
    </template>

    <!-- 正常内容 -->
    <template v-else>
      <!-- 主指标：现行标准 -->
      <div class="mp-stat-hero">
        <div class="mp-hero-glow" />
        <div class="mp-hero-content">
          <span class="mp-hero-label">{{ t('home.current') }}</span>
          <span class="mp-hero-value">{{ error ? '—' : (stats.current ?? 0) }}</span>
          <span class="mp-hero-badge mp-badge mp-badge-success">
            <span class="mp-dot-success" /> 有效
          </span>
        </div>
      </div>

      <!-- 副指标区 -->
      <div class="mp-stat-minis">
        <div class="mp-mini-card">
          <div class="mp-mini-icon mp-mini-warning"><i class="pi pi-hourglass" /></div>
          <div class="mp-mini-label">{{ t('home.pending') }}</div>
          <div class="mp-mini-val text-warning">{{ error ? '—' : (stats.pending ?? 0) }}</div>
        </div>
        <div class="mp-mini-card">
          <div class="mp-mini-icon mp-mini-info"><i class="pi pi-calendar-plus" /></div>
          <div class="mp-mini-label">{{ t('home.upcoming') }}</div>
          <div class="mp-mini-val text-info">{{ error ? '—' : (stats.upcoming ?? 0) }}</div>
        </div>
        <div class="mp-mini-card">
          <div class="mp-mini-icon mp-mini-danger"><i class="pi pi-times-circle" /></div>
          <div class="mp-mini-label">{{ t('home.expired') }}</div>
          <div class="mp-mini-val text-dim">{{ error ? '—' : (stats.expired ?? 0) }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mp-stats-root {
  height: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 14px;
  box-sizing: border-box;
}

/* ── 主指标 ── */
.mp-stat-hero {
  position: relative;
  background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08));
  border: 1px solid rgba(99,102,241,0.25);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.mp-hero-glow {
  position: absolute;
  right: -30px; top: -30px;
  width: 100px; height: 100px;
  background: rgba(99,102,241,0.2);
  border-radius: 50%;
  filter: blur(30px);
}
.mp-hero-content {
  position: relative; z-index: 1;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.mp-hero-label { font-size: 12px; color: var(--text-dim); font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.mp-hero-value { font-size: 42px; font-weight: 800; font-family: var(--mono); color: var(--text-heading); line-height: 1; }
.mp-hero-badge { margin-top: 2px; }

/* ── 副指标 ── */
.mp-stat-minis {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
}
.mp-mini-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  background: var(--surface-raised);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
}
.mp-mini-icon {
  width: 32px; height: 32px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center; font-size: 14px;
}
.mp-mini-warning { background: rgba(245,158,11,0.12); color: var(--warning); }
.mp-mini-info    { background: rgba(59,130,246,0.12); color: var(--info); }
.mp-mini-danger  { background: rgba(239,68,68,0.12); color: var(--danger); }
.mp-mini-label { font-size: 11px; color: var(--text-dim); flex: 1; }
.mp-mini-val { font-size: 18px; font-weight: 700; font-family: var(--mono); }
.text-warning { color: var(--warning); }
.text-info { color: var(--info); }
.text-dim { color: var(--text-dim); }

/* ── 骨架 ── */
.mp-skeleton-main {
  grid-column: 1;
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-lg);
}
.mp-skeleton-sub {
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius);
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
