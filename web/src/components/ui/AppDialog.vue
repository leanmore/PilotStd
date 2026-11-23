<script setup lang="ts">
/**
 * AppDialog — 跨端设计系统（DS）统一弹窗（阶段二 · 模块二骨架）。
 *
 * 规则来源：docs/reference/ui-system.md §12（弹窗规范 / 组件契约表）
 *   - 圆角 --ds-radius-lg（12px，与 §4.1「弹窗 / 面板」一致）
 *   - 头/内容内边距 --space-18 / --space-20（见下方"内边距为什么是 20 而不是 22"）
 *   - header 底部一条 --border 分隔线；标题 --text-heading + --font-weight-semibold
 *   - 关闭按钮：右上角，图标尺寸 --size-20
 *   - 遮罩层：**不新增颜色令牌**，沿用 PrimeVue Aura 默认 mask
 *     （light `rgba(0,0,0,0.4)` / dark `rgba(0,0,0,0.6)`，由主题 preset 的 `mask.background` 提供）。
 *     理由见下方"遮罩层"注释。
 *
 * ── 显式 props vs $attrs 的分界 ──
 * 显式声明业务代码**必用**的 7 个（visible / header / modal / dismissableMask / closable /
 * draggable / bare），因为它们同时是 v-model 与 a11y 的语义锚点，声明出来才有类型提示与契约表可写；
 * 其余（maximizable / position / appendTo / contentStyle / contentClass / breakpoints /
 * blockScroll / closeOnEscape / baseZIndex / pt …）走 `v-bind="$attrs"` 全量透传，
 * 与直接用 PrimeVue Dialog 完全同构。`style` / `class` 也是 $attrs —— 业务代码大量使用
 * `:style="{ width: '360px' }"`（7 处 Dialog 全在用），必须原样落到 `.p-dialog` 根节点上。
 *
 * ── 事件 ──
 * 声明 `update:visible` / `show` / `hide` 三个：`v-model:visible` 依赖前者（若只透传，
 * 声明式 emits 会把监听器从 $attrs 里摘掉，必须手动转发）；后两者是业务侧关闭时清理状态的钩子
 * （TaskManager 用 `@hide="detailTask = null"`）。其余事件（after-hide / maximize / dragstart …）
 * 继续走 $attrs 透传。
 *
 * ── 为什么样式块不带 scoped ──
 * Dialog 的内容渲染在 `<Portal>`（teleport 到 body）里，scoped CSS 的 `[data-v-*]` 作用域属性
 * 无法稳定落到 teleport 后的节点上（与 AppSelect 的 `.p-select-overlay`、AppDatePicker 的
 * `.p-datepicker-panel` 同一限制，见 ui-system.md §11 与那两个组件的注释）。
 * 故本组件用**非 scoped** 的样式块，但所有选择器都以 `.app-dialog` 前缀收口，
 * 效果等价于"只影响 AppDialog 渲染出来的那棵 DOM"，不会污染全局 `.p-dialog`。
 * 未迁移的直接 `<Dialog>` 用法仍由 style.css 的 `.p-dialog` 段负责（迁移完成后可删）。
 *
 * ── 内边距为什么是 --space-20 而不是 22px ──
 * 迁移前 style.css 写的是 `padding: 18px 22px`（水平 22px 在 design-tokens.css 里**没有**对应档位：
 * 间距档位是 1/2/3/4/6/7/8/9/10/12/14/16/18/20/24/30/32/40/44，没有 22）。
 * 两个可选路径：
 *   a) 往 design-tokens.css 加 `--space-22` —— 但本轮 write scope 不含该文件，且 22px 是 off-grid
 *      （非 2/4 的倍数、也不在 8pt 网格上），加档等于给"不可收敛的间距"背书；
 *   b) 取最近的既有档位 --space-20（20px，在 8pt 网格上）—— 视觉差 2px，肉眼不可辨。
 * 按 task-21 的明确指示（"若不存在用 --space-16/--space-20 并说明"）选 b。
 * 竖直方向 18px 有精确令牌 --space-18，原样保留（这是弹窗观感的主要来源）。
 *
 * ── 遮罩层为什么不要 --overlay-backdrop ──
 * 迁移前 style.css 从未覆盖遮罩（`html .p-dialog-mask` 不存在），生产观感就是 Aura 默认值：
 * light 40% / dark 60% 黑。本轮目标是"视觉等价地令牌化"，不是重新设计；新增颜色键会连带
 * 触发 design-tokens.test.ts 的「映射表覆盖全部颜色键」断言与 Win 端令牌同步（gen_win_tokens），
 * 成本高且无视觉需求。若将来确实要调遮罩浓度，按 ui-system.md §5 的三处同步接线
 * （themes.ts 颜色键 + applyThemeToDom + style.css :root 默认层）一次性完成。
 *
 * ── bare 逃生舱 ──
 * 走 PrimeVue 官方 unstyled 模式：零基础视觉（连 p-dialog / p-overlay-mask 类名都不生成），
 * 外观（含遮罩）全部由宿主负责。用于完全自定义的浮层结构。
 */
import Dialog from 'primevue/dialog'

defineOptions({ name: 'AppDialog', inheritAttrs: false })

withDefaults(
  defineProps<{
    /** 受控显隐（v-model:visible）；与 PrimeVue Dialog 的 visible 同义 */
    visible?: boolean
    /** 标题文案（也可用 #header 插槽完全接管标题区）
     *  类型刻意是 `string`（不是 `string | null`）：PrimeVue Dialog 的 d.ts 声明为
     *  `header?: string | undefined`，传 null 会在 vue-tsc 阶段报 TS2322；
     *  运行时 BaseDialog 的 default 虽是 null，但"不传"与"传 undefined"行为等价，
     *  故这里用 undefined 表示"无标题"，保住严格类型检查。 */
    header?: string
    /** 模态：true 时渲染遮罩、锁定焦点与页面滚动 */
    modal?: boolean
    /** 点击遮罩关闭（仅 modal 下生效，与 PrimeVue 语义一致） */
    dismissableMask?: boolean
    /** 显示右上角关闭按钮 */
    closable?: boolean
    /** 头部可拖拽（PrimeVue 默认 true） */
    draggable?: boolean
    /** 裸样式：不施加任何基础视觉，props/事件/插槽仍全量透传 */
    bare?: boolean
  }>(),
  {
    visible: false,
    header: undefined,
    modal: false,
    dismissableMask: false,
    closable: true,
    draggable: true,
    bare: false,
  },
)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'show'): void
  (e: 'hide'): void
}>()

/** 关闭/遮罩点击/ESC 都经 PrimeVue 的 update:visible 回流，这里原样转给调用方 */
function onUpdateVisible(value: boolean): void {
  emit('update:visible', value)
}
</script>

<template>
  <Dialog
    v-bind="$attrs"
    :visible="visible"
    :header="header"
    :modal="modal"
    :dismissable-mask="dismissableMask"
    :closable="closable"
    :draggable="draggable"
    :unstyled="bare"
    :class="bare ? ['app-dialog--bare'] : ['app-dialog']"
    @update:visible="onUpdateVisible"
    @show="emit('show')"
    @hide="emit('hide')"
  >
    <!-- 插槽全量动态透传：默认、#header、#footer、#container、#closebutton、#maximizebutton、
         #closeicon、#maximizeicon（PrimeVue 4.5 的图标插槽不叫 #icons，见 ui-system.md §12.4）。
         动态 v-for 保证任何具名插槽零遗漏转发；`slotProps ?? {}` 兜住无参插槽。 -->
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </Dialog>
</template>

<style>
/* ═══ 弹窗本体（DS 口径，与迁移前 style.css 的 .p-dialog 段逐值等价）═══
   非 scoped：内容在 Portal 里（见文件头"为什么样式块不带 scoped"）。
   `html` 前缀用于压过 style.css 的 `.p-dialog` 段与 Aura 运行时注入的组件作用域 token
   （与 style.css 里既有 RETAINED 覆盖同一手法）。 */
html .app-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-lg);
  box-shadow: var(--shadow-lg);
}

html .app-dialog .p-dialog-header {
  padding: var(--space-18) var(--space-20);
  border-bottom: 1px solid var(--border);
  color: var(--text-heading);
  font-weight: var(--font-weight-semibold);
}

html .app-dialog .p-dialog-content {
  padding: var(--space-18) var(--space-20);
}

/* 关闭按钮：位置由 Aura 默认提供（header 右侧的 .p-dialog-header-actions 内，即右上角），
   这里只收敛图标尺寸到 --size-20 与颜色层级。
   刻意**不**给按钮本体设 width/height：Aura 的关闭按钮是 text+rounded 的图标按钮，
   硬设 20×20 会把它的内边距压没、点击热区缩到 20px（< WCAG 2.5.8 的 24px 最小目标），
   视觉也会比相邻的标题行偏小。只改图标字号既满足"右上角 --size-20 图标"的口径，
   又保住热区。 */
html .app-dialog .p-dialog-close-button .p-button-icon {
  font-size: var(--size-20);
  color: var(--text-secondary);
}
html .app-dialog .p-dialog-close-button:hover .p-button-icon {
  color: var(--text);
}
</style>
