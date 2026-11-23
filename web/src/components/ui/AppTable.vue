<script setup lang="ts">
/**
 * AppTable — 跨端设计系统（DS）统一数据表格（阶段二 · 模块二骨架）。
 *
 * 规则来源：docs/reference/ui-system.md §12（表格规范 / 组件契约表）
 *   - 表头：底 --surface-raised、字 --text、字号 --font-size-11、字重 --font-weight-semibold、
 *     大写 + 字距 0.6px、内边距 --space-10 / --space-14（**与迁移前 style.css 逐值等价**）
 *   - 行：底 --surface、分隔线 --border-light、内边距 --space-9 / --space-14、字号 --font-size-13
 *   - 斑马纹：--surface-raised；行 hover：--selected（沿用迁移前观感，见下方"斑马纹"注释）
 *   - 圆角：--ds-radius-md（旧 --radius 10px 冻结，按 §4.1 收敛到 8px）
 *
 * ── 为什么 props 全部走 $attrs，只显式声明 bare ──
 * DataTable 的 props/事件有 80+ 个（value / rows / paginator / totalRecords / stripedRows /
 * loading / dataKey / selectionMode / v-model:selection / expandedRows / editMode / @page /
 * @sort / @rowSelect / @cell-edit-complete …），逐条声明等于抄一遍 PrimeVue 的 d.ts：
 * 漏一个就静默失效（值落到 DOM attribute 上、不报错、测试也测不到），维护成本远高于收益。
 * 故 `inheritAttrs: false` + `v-bind="$attrs"` 全量透传 —— 语义与直接用 PrimeVue DataTable
 * **完全同构**，迁移时只需改标签名（`<DataTable>` → `<AppTable>`），props/事件一个都不用动。
 * 唯一被显式接管的键是 `bare`（DS 逃生舱）与 `class`（合并 DS 类名，不覆盖业务 class）。
 *
 * ── 为什么 slots 用 v-for 动态透传 ──
 * DataTable 的插槽分两层：
 *   1. 组件级：#header / #footer / #empty / #loading / #paginatorstart / #paginatorend …
 *   2. Column 级（写在默认插槽的 <Column> 里）：#body / #editor / #filter / #groupheader …
 * 第 2 层的插槽由 Column 自己消费，第 1 层必须原样交给 DataTable。逐条列举同样会漏
 * （PrimeVue 4.5 的 paginator 图标插槽就有 6 个），故统一用 `v-for="(_, name) in $slots"`
 * 动态转发：任何新增/未列举的具名插槽都自动透传，零遗漏。
 * `slotProps ?? {}`：无插槽参数时 Vue 传入 undefined，直接 v-bind 会报 "Cannot read properties"。
 *
 * ── bare 逃生舱 ──
 * 走 PrimeVue 官方 unstyled 模式：零基础视觉（连 p-datatable 类名都不生成），外观由宿主全权负责。
 * 用于树形表格 / 合并单元格 / 行内编辑这类需要完全自定义表格结构的场景。
 * 不用 CSS 逐条清零，避免把 0 / transparent / none 这类结构性字面量再写进组件
 * （G-055 的 ds-skeleton 基线只登记真正需要的）。
 */
import DataTable from 'primevue/datatable'

defineOptions({ name: 'AppTable', inheritAttrs: false })

withDefaults(
  defineProps<{
    /** 裸样式：不施加任何基础视觉，props/事件/插槽仍全量透传 */
    bare?: boolean
  }>(),
  { bare: false },
)
</script>

<template>
  <DataTable
    v-bind="$attrs"
    :unstyled="bare"
    :class="bare ? ['app-table--bare'] : ['app-table']"
  >
    <!-- 插槽全量动态透传：默认插槽（<Column>）、#header、#empty、#footer、#groupheader、
         #expansion、#loading 以及 PrimeVue 分页器图标等未列举的具名插槽 -->
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </DataTable>
</template>

<style scoped>
/* ═══ 表格本体（DS 口径，与 style.css 的 .p-datatable 段逐值等价）═══
   说明：style.css 保留同一组规则，用于**尚未迁移**的直接 <DataTable> 用法
   （如 TaskManager 的两张表）；AppTable 渲染时本文件的 :deep() 因多一个 .app-table 类
   而特异性更高，覆盖结果与 style.css 一致（唯一有意的差异是圆角：10px → --ds-radius-md 8px，
   见 ui-system.md §4.1「旧的 --radius 冻结」）。B1–B4 批次迁移完成后可删除 style.css 段。 */
.app-table {
  background: var(--surface);
  border-radius: var(--ds-radius-md);
  overflow: hidden;
}

.app-table :deep(.p-datatable-header) {
  background: var(--surface);
  border-color: var(--border);
  color: var(--text);
  padding: var(--space-12) var(--space-16);
}

/* RETAINED: DataTable header text override
   Reason: Aura 组件作用域 token（--p-datatable-header-cell-color 等）为解析后直接值 #334155，
   root 级 --p-content-color 注入无法覆盖（P1 实证）；--text-dim 作表头色浅色主题 2.4-2.6:1 不达标，
   改用 --text 后 ≈7:1（浅色深字/深色浅字自适应），保留加粗+大写维持表头层级。
   See: docs/technical-debt.md（Tech-Debt #8；原始调研报告已归档至 docs/.local/archive/2026-10-24/，未入库）
   （原文随规则一起从 style.css 迁到本文件；style.css 的旧副本仍保留给未迁移表格。） */
.app-table :deep(.p-datatable-thead > tr > th) {
  background: var(--surface-raised);
  color: var(--text);
  border-color: var(--border);
  font-size: var(--font-size-11);
  font-weight: var(--font-weight-semibold);
  text-transform: uppercase;
  /* 字距无对应令牌（0.6px 是唯一的字距档位），按"保留现值"处理：
     G-055 只审计 font-size / font-weight / padding 等已映射属性，letter-spacing 不在其列。 */
  letter-spacing: 0.6px;
  padding: var(--space-10) var(--space-14);
}

.app-table :deep(.p-datatable-tbody > tr) {
  background: var(--surface);
  transition: background var(--transition);
}

.app-table :deep(.p-datatable-tbody > tr > td) {
  border-color: var(--border-light);
  color: var(--text);
  padding: var(--space-9) var(--space-14);
  font-size: var(--font-size-13);
}

.app-table :deep(.p-datatable-tbody > tr:hover) {
  background: var(--selected);
}

/* 斑马纹沿用 --surface-raised（迁移前观感），**不新增 --table-stripe**：
   现有偶数行是极浅的抬升面，与 hover 的 --selected（主色 8% 透明）是两级不同的视觉信号；
   若把斑马纹也改成 --selected，hover 行会与相邻斑马行同色，"当前悬停哪一行"反而不可辨
   （与 ui-system.md §11.3 输入框 hover 不改底色的取舍同源）。 */
.app-table :deep(.p-datatable-tbody > tr:nth-child(even)) {
  background: var(--surface-raised);
}

.app-table :deep(.p-datatable-emptymessage td) {
  color: var(--text-dim);
  padding: var(--space-32);
  text-align: center;
  font-size: var(--font-size-13);
}

/* 分页器（.p-paginator*）刻意留在 style.css：
   1. 它是 PrimeVue Paginator 的内部结构，与表格本体解耦，放全局段对"未迁移表格"同样生效；
   2. 分页按钮的 32px 高度在 design-tokens.css 里没有独立语义令牌（唯一同值是
      --icon-tile-sm「仪表盘图标方块」），写进组件会被 G-055 判成 A 类可映射硬编码，
      而挪用 --icon-tile-sm 属语义错配。style.css 的 .p-* 段属 C 类 RETAINED 豁免，留在那里零风险。 */
</style>
