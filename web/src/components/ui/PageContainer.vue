<script setup lang="ts">
/**
 * PageContainer — 跨端设计系统（DS）统一页面容器（阶段三 · 模块三骨架）。
 *
 * 规则来源：docs/reference/ui-system.md §13.1（PageContainer 规范）
 *
 * ── 职责边界（重要，避免双倍内边距）──
 * 两层容器的分工必须分清，否则页面会被"左右各 36px + 各 32px"挤成很窄一条：
 *   - `AppLayout` 的 `.content-inner`：**视口级**留白 —— 负责「内容区与浏览器窗口边缘」
 *     的距离（桌面 32px/36px、平板 24px/20px、移动 16px/12px），以及 max-width:1600px 居中。
 *   - `PageContainer`（本组件）：**页面内**留白 —— 负责「本页内容块之间」的垂直节奏、
 *     页面标题的统一排版、以及本页自己的最大宽度（很多页比 1600px 窄得多，如 900px）。
 *
 * 故本组件**默认不加左右内边距**（交给 .content-inner），只负责：
 *   1. 可选标题（h2.page-title 统一样式，消除 8 个 views 里逐字重复的那段 CSS）；
 *   2. 可选 maxWidth（页面级内容宽度上限，如 900 / 1000 / 1100）；
 *   3. `#actions` 插槽（标题右侧操作区）；
 *   4. `flush`：完全去掉内边距（全宽页面，如仪表盘 grid）。
 * 若某页确实需要自己的左右留白（例如嵌在 Tab 里的子页），用 `padded` 显式开启。
 *
 * ── 为什么 padding 用「三断点 + 令牌」而不是写死 ──
 * 与 .content-inner 的断点保持一致（1023px / 767px），保证两层在同一个断点切换，
 * 不会出现"外层已切到移动档、内层还是桌面档"的错位。
 */
import { computed } from 'vue'

defineOptions({ name: 'PageContainer', inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    /** 页面内容最大宽度（px）。默认不限制（由 .content-inner 的 1600px 兜底） */
    maxWidth?: number | string | null
    /** 页面标题（传了才渲染 h2.page-title；也可用 #title 插槽完全接管） */
    title?: string | null
    /** 副标题（标题下方的小字说明） */
    subtitle?: string | null
    /** 完全去掉内边距（全宽页面，如仪表盘 grid 布局） */
    flush?: boolean
    /** 显式开启左右内边距（默认关闭，左右留给 .content-inner，避免双倍留白） */
    padded?: boolean
  }>(),
  {
    maxWidth: null,
    title: null,
    subtitle: null,
    flush: false,
    padded: false,
  },
)

/** 把 maxWidth 归一成 CSS 值：数字补 px，字符串原样，null 表示不限制 */
const maxWidthStyle = computed(() => {
  const mw = props.maxWidth
  if (mw == null || mw === '') return undefined
  return typeof mw === 'number' ? `${mw}px` : mw
})
</script>

<template>
  <div
    v-bind="$attrs"
    class="page-container"
    :class="{ 'page-container--flush': flush, 'page-container--padded': padded }"
    :style="maxWidthStyle ? { maxWidth: maxWidthStyle } : undefined"
  >
    <!-- 标题区：title prop 走默认排版；#title / #actions 插槽可完全接管 -->
    <div v-if="title || subtitle || $slots.title || $slots.actions" class="page-container__header">
      <div class="page-container__heading">
        <slot name="title">
          <h2 v-if="title" class="page-title">{{ title }}</h2>
        </slot>
        <p v-if="subtitle" class="page-container__subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="page-container__actions">
        <slot name="actions" />
      </div>
    </div>

    <slot />
  </div>
</template>

<style scoped>
/* ── 容器：默认只做「页面内」垂直节奏，左右留白交给 .content-inner ── */
.page-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-16);
  /* 左右内边距默认 0：见文件头「职责边界」。显式 padded 时才加。 */
  padding-block: 0;
  padding-inline: 0;
}

/* 显式开启左右留白（与 .content-inner 同档，供 Tab 内嵌子页使用） */
.page-container--padded {
  padding-inline: var(--space-32);
}

/* 全宽页面：去掉一切内边距 */
.page-container--flush {
  gap: 0;
  padding-block: 0;
  padding-inline: 0;
}

/* ── 标题区：标题 + 副标题在左，操作区在右 ── */
.page-container__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-16);
  margin-bottom: var(--space-4);
}

.page-container__heading {
  min-width: 0;
}

/* 统一样式：消除 8 个 views 里逐字重复的 .page-title 定义
   （原值：margin 0 0 --space-20；20px/600/--text-heading） */
.page-title {
  margin: 0;
  font-size: var(--font-size-20);
  font-weight: var(--font-weight-semibold);
  color: var(--text-heading);
  line-height: var(--line-height-snug);
}

.page-container__subtitle {
  margin: var(--space-4) 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-13);
}

.page-container__actions {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  flex-shrink: 0;
}

/* ── 响应式：与 AppLayout 的 .content-inner 保持同一断点 ── */
@media (max-width: 1023px) {
  .page-container--padded {
    padding-inline: var(--space-24);
  }
}

@media (max-width: 767px) {
  .page-container {
    gap: var(--space-12);
  }
  .page-container--padded {
    padding-inline: var(--space-16);
  }
  .page-container__header {
    flex-direction: column;
    gap: var(--space-8);
  }
}
</style>
