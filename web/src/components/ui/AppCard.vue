<script setup lang="ts">
/**
 * AppCard — 跨端设计系统（DS）统一卡片容器（阶段三 · 模块三骨架）。
 *
 * 规则来源：docs/reference/ui-system.md §13.2（卡片规范）
 *   - 阴影：默认 --shadow-sm；`elevated` 时 --shadow-md（两级足够，不引入第三档）
 *   - 圆角：--ds-radius-md（与按钮/输入框/表格同一口径，见 §4.1）
 *   - 内边距：--space-20（内容区），标题区与页脚区共用同一水平内边距
 *   - 边框：1px solid var(--border)（与 Aura 默认一致，保证浅色主题下有清晰边界）
 *
 * ── 为什么 props 全部走 $attrs，只显式声明 elevated / bare ──
 * 与 AppTable 同一理由：PrimeVue Card 的 props 虽少，但业务侧会传
 * `class` / `style` / `data-*` / `aria-*`，逐条声明等于抄 d.ts，
 * 漏一个就静默失效。故 `inheritAttrs: false` + `v-bind="$attrs"` 全量透传，
 * 语义与直接用 PrimeVue Card **完全同构**，迁移只需改标签名。
 * 唯一被显式接管的键是 `elevated`（DS 阴影档）与 `bare`（DS 逃生舱）。
 *
 * ── 为什么 slots 用 v-for 动态透传 ──
 * Card 的插槽有 #header / #title / #subtitle / #content / #footer 五个，
 * 业务代码实际用到 #title / #content / #footer 居多，但逐条列举会漏
 * （例如将来用 #subtitle）。动态转发零遗漏，`slotProps ?? {}` 兜住无参插槽。
 *
 * ── bare 逃生舱 ──
 * 走 PrimeVue 官方 unstyled 模式：零基础视觉（连 p-card 类名都不生成），
 * 外观由宿主全权负责。用于仪表盘这类需要完全自定义卡片结构的场景。
 */
import Card from 'primevue/card'

defineOptions({ name: 'AppCard', inheritAttrs: false })

withDefaults(
  defineProps<{
    /** 抬升一档阴影（--shadow-md）：用于需要与背景明显分离的浮层式卡片 */
    elevated?: boolean
    /** 裸样式：不施加任何基础视觉，props/事件/插槽仍全量透传 */
    bare?: boolean
  }>(),
  { elevated: false, bare: false },
)
</script>

<template>
  <Card
    v-bind="$attrs"
    :unstyled="bare"
    :class="bare
      ? ['app-card--bare']
      : ['app-card', { 'app-card--elevated': elevated }]"
  >
    <!-- 插槽全量动态透传：#header / #title / #subtitle / #content / #footer
         以及任何未列举的具名插槽 -->
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </Card>
</template>

<style scoped>
/* ═══ 卡片本体（DS 口径）═══
   说明：style.css 保留 .p-card 段服务尚未迁移的直接 <Card> 用法；
   AppCard 渲染时本文件的 :deep() 因多一个 .app-card 类而特异性更高。 */
.app-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.app-card--elevated {
  box-shadow: var(--shadow-md);
}

/* ── 标题区：与内容区共用水平内边距，底部加分隔线 ── */
.app-card :deep(.p-card-title) {
  margin: 0;
  padding: var(--space-16) var(--space-20);
  border-bottom: 1px solid var(--border);
  color: var(--text-heading);
  font-size: var(--font-size-15);
  font-weight: var(--font-weight-semibold);
}

.app-card :deep(.p-card-subtitle) {
  margin: 0;
  padding: 0 var(--space-20) var(--space-12);
  color: var(--text-secondary);
  font-size: var(--font-size-12);
}

/* ── 内容区 ── */
.app-card :deep(.p-card-body) {
  padding: 0;
}

.app-card :deep(.p-card-content) {
  padding: var(--space-20);
}

/* 有标题时内容区上内边距收一档（标题区已有自己的下边距与分隔线） */
.app-card :deep(.p-card-title) + :deep(.p-card-content) {
  padding-top: var(--space-16);
}

/* ── 页脚区 ── */
.app-card :deep(.p-card-footer) {
  padding: var(--space-12) var(--space-20);
  border-top: 1px solid var(--border);
}
</style>
