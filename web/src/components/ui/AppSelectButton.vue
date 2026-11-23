<script setup lang="ts">
/**
 * AppSelectButton — 跨端设计系统（DS）**分段单选**控件（阶段二 · 模块一扩展）。
 *
 * 为什么需要它（与 AppSelect 的分工，**不得互相替代**）：
 *   - `AppSelect` = 下拉选择（折叠面板），适合选项多、低频的场景；
 *   - `AppSelectButton` = **分段单选**（所有选项同时可见、一键切换），适合 2–4 个互斥枚举值
 *     的高频切换（如「追加 / 替换」「自动 / Playwright」「手动 / CookieCloud」）。
 *   把分段单选改成下拉会**改变交互形态**（多一次点击、看不到当前全集），
 *   故 C3 批次不迁到 AppSelect，而是新增本封装（门禁禁止业务代码直接 import
 *   `primevue/selectbutton`，见 custom/no-raw-input）。
 *
 * 规则来源：docs/reference/ui-system.md §11.5 组件契约
 *   （本组件为 C3 批次新增的第六个 App* 输入类封装，契约表行由文档 owner 在 §11.5 补登，
 *     本任务只改 components/ 与 ui/，不动 docs/）
 *   - 三档尺寸：l / m / s → 高度取 --input-height-*（与输入框同档，便于与 AppInput 并排）
 *   - 圆角统一 --ds-radius-md；禁用态取 --disabled-bg / --disabled-text（A-53 接线口径）
 *   - 选中态取 --primary-bg / --primary-border / --primary（与 style.css 中
 *     `.p-selectbutton .p-button.p-highlight` 的历史意图一致，那里是 PrimeVue 3 的类名，
 *     PrimeVue 4 已改为 `.p-togglebutton`，故视觉收口到本组件的 :deep 段）
 *
 * 视觉实现说明：PrimeVue 4 的 SelectButton 由 `div.p-selectbutton`（role=group）+
 *   若干 `button.p-togglebutton` 组成，Aura 默认是「灰轨道 + 白滑块」的两层结构
 *   （选中态落在 `.p-togglebutton-content` 的底色上）。DS 口径是**扁平分段**：
 *   轨道透明、选中项直接换底色，故这里把 content 背景置为透明，选中态落在 button 上。
 *
 * bare 逃生舱：走 PrimeVue 官方 unstyled 模式（零基础视觉，不写任何清零字面量）。
 */
import { computed } from 'vue'
import SelectButton from 'primevue/selectbutton'

defineOptions({ name: 'AppSelectButton', inheritAttrs: false })

type SelectButtonSize = 'l' | 'm' | 's'

const props = withDefaults(
  defineProps<{
    /** 受控值（v-model）：单选回传 optionValue 对应值；multiple 回传数组 */
    modelValue?: unknown
    /** 选项数组（原样透传给 SelectButton） */
    options?: unknown[]
    /** 选项文案字段或取值函数 */
    optionLabel?: string | ((data: unknown) => string)
    /** 选项值字段或取值函数（不传则回传整个 option 对象） */
    optionValue?: string | ((data: unknown) => unknown)
    /** 选项禁用标记字段或取值函数 */
    optionDisabled?: string | ((data: unknown) => boolean)
    /** 多选（分段多选；默认单选） */
    multiple?: boolean
    /** 尺寸档：l / m / s（默认 m）；映射到 PrimeVue 的 large / 默认 / small */
    size?: SelectButtonSize
    disabled?: boolean
    invalid?: boolean
    /** 裸样式：不施加任何基础视觉 */
    bare?: boolean
  }>(),
  {
    modelValue: undefined,
    options: () => [],
    optionLabel: undefined,
    optionValue: undefined,
    optionDisabled: undefined,
    multiple: false,
    size: 'm',
    disabled: false,
    invalid: false,
    bare: false,
  },
)

const emit = defineEmits<{ (e: 'update:modelValue', value: unknown): void }>()

/**
 * DS 三档 → PrimeVue 两档：s→small、l→large、m→不传（Aura 默认）。
 * 只借它的字号/内边距档，高度由本组件的 --input-height-* 决定。
 */
const primeSize = computed<'small' | 'large' | undefined>(() => {
  if (props.size === 's') return 'small'
  if (props.size === 'l') return 'large'
  return undefined
})

function onUpdate(value: unknown): void {
  emit('update:modelValue', value)
}
</script>

<template>
  <SelectButton
    v-bind="$attrs"
    :model-value="modelValue"
    :options="options"
    :option-label="optionLabel"
    :option-value="optionValue"
    :option-disabled="optionDisabled"
    :multiple="multiple"
    :size="primeSize"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :class="bare
      ? ['app-selectbutton--bare']
      : ['app-selectbutton', `app-selectbutton--${size}`, {
          'app-selectbutton--invalid': invalid,
          'app-selectbutton--disabled': disabled,
        }]"
    @update:model-value="onUpdate"
  />
</template>

<style scoped>
/* ── 轨道（root，role=group）：透明底 + DS 圆角，视觉落在分段按钮上 ── */
.app-selectbutton {
  display: inline-flex;
  gap: var(--space-2);
  border-radius: var(--ds-radius-md);
}

/* ── 尺寸档：分段按钮高度与输入框同档，便于与 AppInput 并排对齐 ── */
.app-selectbutton--l :deep(.p-togglebutton) {
  height: var(--input-height-lg);
  padding-inline: var(--space-16);
  font-size: var(--font-size-15);
}
.app-selectbutton--m :deep(.p-togglebutton) {
  height: var(--input-height-md);
  padding-inline: var(--space-14);
  font-size: var(--font-size-13);
}
.app-selectbutton--s :deep(.p-togglebutton) {
  height: var(--input-height-sm);
  padding-inline: var(--space-12);
  font-size: var(--font-size-12);
}

/* ── 分段按钮本体：默认态 ── */
.app-selectbutton :deep(.p-togglebutton) {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  color: var(--text);
  transition: background-color var(--transition), border-color var(--transition), color var(--transition);
}

/* 内容层透明：DS 是扁平分段，选中底色直接落在 button 上（不叠 Aura 的白滑块） */
.app-selectbutton :deep(.p-togglebutton-content) {
  background: transparent;
  padding: 0;
}

/* ── 选中态：主色浅底 + 主色描边 + 主色文字 ── */
.app-selectbutton :deep(.p-togglebutton.p-togglebutton-checked) {
  background: var(--primary-bg);
  border-color: var(--primary-border);
  color: var(--primary);
}
.app-selectbutton :deep(.p-togglebutton.p-togglebutton-checked .p-togglebutton-content) {
  background: transparent;
  color: var(--primary);
}

/* ── 四态：hover / focus / invalid / disabled ── */
.app-selectbutton :deep(.p-togglebutton:not(:disabled):hover) {
  border-color: var(--text-dim);
}
.app-selectbutton :deep(.p-togglebutton:not(:disabled):hover.p-togglebutton-checked) {
  border-color: var(--primary-border);
}
.app-selectbutton :deep(.p-togglebutton:focus-visible) {
  box-shadow: var(--focus-ring);
  outline: none;
}

.app-selectbutton--invalid :deep(.p-togglebutton) {
  border-color: var(--danger);
}

.app-selectbutton--disabled :deep(.p-togglebutton) {
  background: var(--disabled-bg);
  border-color: var(--border);
  color: var(--disabled-text);
  cursor: not-allowed;
}
</style>
