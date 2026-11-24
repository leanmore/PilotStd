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
    stats.value = await getStats('/')
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
            <span class="mp-dot-success" /> {{ t('dashboard.stats.valid') }}
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
  gap: var(--space-10);
  padding: var(--space-14);
  box-sizing: border-box;
}

/* ── 主指标 ── */
.mp-stat-hero {
  position: relative;
  /* TODO: [Design Debt] A-52 — linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08)) 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08));
  /* TODO: [Design Debt] A-52 — 1px solid rgba(99,102,241,0.25) 无精确令牌，暂不替换，待定令牌后统一处理 */
  border: 1px solid rgba(99,102,241,0.25);
  border-radius: var(--ds-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.mp-hero-glow {
  position: absolute;
  right: -30px; top: -30px;
  /* TODO: [Design Debt] A-52 — 100px 无精确令牌，暂不替换，待定令牌后统一处理 */
  width: 100px; height: 100px;
  background: var(--primary-border);
  border-radius: 50%;
  filter: blur(30px);
}
.mp-hero-content {
  position: relative; z-index: 1;
  display: flex; flex-direction: column; align-items: center; gap: var(--space-6);
}
.mp-hero-label { font-size: var(--font-size-12); color: var(--text-dim); font-weight: var(--font-weight-medium); text-transform: uppercase; letter-spacing: 0.05em; }
.mp-hero-value { font-size: var(--font-size-42); font-weight: var(--font-weight-extrabold); font-family: var(--mono); color: var(--text-heading); line-height: var(--line-height-none); }
.mp-hero-badge { margin-top: var(--space-2); }

/* ── 副指标 ── */
.mp-stat-minis {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-6);
}
.mp-mini-card {
  display: flex; align-items: center; gap: var(--space-10);
  padding: var(--space-8) var(--space-12);
  background: var(--surface-raised);
  border: 1px solid var(--border-light);
  border-radius: var(--ds-radius-md);
}
.mp-mini-icon {
  width: 32px; height: var(--icon-tile-sm); border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center; font-size: var(--font-size-14);
}
.mp-mini-warning { background: var(--warning-bg); color: var(--warning); }
.mp-mini-info    { background: var(--info-bg); color: var(--info); }
.mp-mini-danger  { background: var(--danger-bg); color: var(--danger); }
.mp-mini-label { font-size: var(--font-size-11); color: var(--text-dim); flex: 1; }
.mp-mini-val { font-size: var(--font-size-18); font-weight: var(--font-weight-bold); font-family: var(--mono); }
.text-warning { color: var(--warning); }
.text-info { color: var(--info); }
.text-dim { color: var(--text-dim); }

/* ── 骨架 ──
   为什么保留自有骨架而不换成 <AppLoading variant="skeleton">：
   本卡片的骨架是**两栏网格**（1 个主块 + 3 个副块，grid-column 定位），
   而 AppLoading 的骨架是**竖排列表**（单列若干条）。换成通用骨架会丢掉网格占位，
   加载完成时卡片高度与位置都会跳动，反而劣化体验。
   故保留结构，只把渐变动画与令牌口径对齐 AppLoading（避免两套 shimmer 实现）。 */

.mp-skeleton-main {
  grid-column: 1;
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--ds-radius-md);
}
.mp-skeleton-sub {
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--ds-radius-md);
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
