<script setup lang="ts">
/**
 * AppLoading — 跨端设计系统（DS）统一加载态（阶段三 · 模块四）。
 *
 * 规则来源：docs/reference/ui-system.md §14.2（加载态规范）
 *
 * ── 三种形态，一个组件 ──
 * 迁移前全站并存三套加载态（`ProgressSpinner` 6 处、手写 skeleton 6 处、
 * `v-if="loading"` 文本占位 5 处），观感与尺寸各不相同。本组件收口为：
 *   - `variant="spinner"`（默认）：转圈 + 可选文案，用于**短时**操作（<1s，如按钮触发的保存）；
 *   - `variant="skeleton"`：骨架屏（若干条灰条），用于**列表/卡片首屏**（>1s 的取数）；
 *   - `variant="inline"`：仅一行小字 + 小转圈，用于**表格/区块内嵌**（不打断布局）。
 *
 * ── 为什么 skeleton 要能配 `rows` ──
 * 骨架屏的核心价值是「占位尺寸接近真实内容」，避免加载完成后布局跳动。
 * 故 `rows` 控制条数、`rowHeight` 控制单条高度，业务按实际列表行数传。
 *
 * ── 为什么不用 PrimeVue 的 ProgressSpinner ──
 * 它的尺寸/颜色只能靠 CSS 字面量覆盖（PrimeVue 4.5.5 的 ProgressSpinner 没有 size prop，
 * 见 A-51 的实测记录），而 DS 要求所有尺寸取令牌。这里用纯 CSS 圆环 + 令牌，
 * 既满足 G-055（无字面量）又便于统一。
 */
import { computed } from 'vue'

defineOptions({ name: 'AppLoading' })

type LoadingVariant = 'spinner' | 'skeleton' | 'inline'
type LoadingSize = 'l' | 'm' | 's'

const props = withDefaults(
  defineProps<{
    /** 形态：转圈 / 骨架屏 / 内嵌小字 */
    variant?: LoadingVariant
    /** 尺寸档（spinner 与 inline 生效；skeleton 由 rows/rowHeight 决定） */
    size?: LoadingSize
    /** 文案（为空则不显示文字） */
    label?: string
    /** 骨架屏条数（仅 skeleton） */
    rows?: number
    /** 骨架屏单条高度（仅 skeleton，取令牌名或数字 px） */
    rowHeight?: string | number
    /** 占满父容器（spinner 垂直居中用） */
    block?: boolean
  }>(),
  {
    variant: 'spinner',
    size: 'm',
    label: '',
    rows: 3,
    rowHeight: 'm',
    block: false,
  },
)

/** spinner / inline 的尺寸（圆环直径与描边宽，全部取令牌） */
const sizeClass = computed(() => `app-loading--${props.size}`)

/** 骨架屏单条高度：数字补 px，字符串原样（支持传令牌名对应的类） */
const rowHeightStyle = computed(() => {
  const h = props.rowHeight
  if (typeof h === 'number') return { height: `${h}px` }
  // 预设档位：s/m/l 映射到令牌高度
  const PRESET: Record<string, string> = {
    s: 'var(--size-8)',
    m: 'var(--size-12)',
    l: 'var(--size-16)',
  }
  return { height: PRESET[h] ?? h }
})
</script>

<template>
  <div
    v-if="variant === 'spinner'"
    class="app-loading app-loading--spinner"
    :class="[sizeClass, { 'app-loading--block': block }]"
    role="status"
    aria-live="polite"
  >
    <span class="app-loading__ring" aria-hidden="true" />
    <span v-if="label" class="app-loading__label">{{ label }}</span>
  </div>
  <div
    v-else-if="variant === 'skeleton'"
    class="app-loading app-loading--skeleton"
    role="status"
    aria-live="polite"
  >
    <span
      v-for="i in rows"
      :key="i"
      class="app-loading__bar"
      :style="rowHeightStyle"
      aria-hidden="true"
    />
    <span class="app-loading__sr">{{ label || 'loading' }}</span>
  </div>
  <span v-else class="app-loading app-loading--inline" :class="sizeClass" role="status" aria-live="polite">
    <span class="app-loading__ring" aria-hidden="true" />
    <span v-if="label" class="app-loading__label">{{ label }}</span>
  </span>
</template>

<style scoped>
/* ── 通用：水平居中 + 间距 ── */
.app-loading {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
  color: var(--text-secondary);
  font-size: var(--font-size-13);
}

.app-loading--block {
  display: flex;
  justify-content: center;
  width: 100%;
  padding: var(--space-32) 0;
}

/* ── 转圈：纯 CSS 圆环，描边色取令牌 ── */
.app-loading__ring {
  display: inline-block;
  border-radius: 50%;
  border-style: solid;
  border-color: var(--border);
  border-top-color: var(--primary);
  animation: app-loading-spin 0.7s linear infinite;
  flex-shrink: 0;
}

/* 尺寸档：直径 × 描边宽（三档全部取令牌） */
.app-loading--s .app-loading__ring {
  width: var(--size-14);
  height: var(--size-14);
  border-width: 2px;
}
.app-loading--m .app-loading__ring {
  width: var(--size-20);
  height: var(--size-20);
  border-width: 2px;
}
.app-loading--l .app-loading__ring {
  width: var(--size-24);
  height: var(--size-24);
  border-width: 3px;
}

@keyframes app-loading-spin {
  to {
    transform: rotate(360deg);
  }
}

/* 尊重「减少动效」偏好：动画改为静态淡入，避免前庭不适 */
@media (prefers-reduced-motion: reduce) {
  .app-loading__ring {
    animation: none;
    border-top-color: var(--primary);
  }
  .app-loading__bar {
    animation: none;
  }
}

.app-loading__label {
  color: var(--text-secondary);
  font-size: var(--font-size-13);
}

/* ── 内嵌形态：更小、无额外间距 ── */
.app-loading--inline {
  gap: var(--space-6);
  font-size: var(--font-size-12);
}
.app-loading--inline .app-loading__label {
  font-size: var(--font-size-12);
}

/* ── 骨架屏：竖向堆叠灰条，带微光扫过动画 ── */
.app-loading--skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  width: 100%;
}

.app-loading__bar {
  display: block;
  width: 100%;
  border-radius: var(--ds-radius-sm);
  background: linear-gradient(
    90deg,
    var(--surface-raised) 25%,
    var(--border-light) 37%,
    var(--surface-raised) 63%
  );
  background-size: 400% 100%;
  animation: app-loading-shimmer 1.4s ease infinite;
}

@keyframes app-loading-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

/* 读屏专用（视觉隐藏但可被朗读） */
.app-loading__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
