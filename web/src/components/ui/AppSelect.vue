<script setup lang="ts" generic="T = unknown">
/**
 * AppSelect — 跨端设计系统（DS）下拉选择（阶段二 · 模块一骨架）。
 *
 * 规则来源：docs/reference/ui-system.md「表单输入控件」
 *   - 三档尺寸：l / m / s，外框高度取 --input-height-*（语义独立于 --btn-height-*）
 *   - 圆角 --ds-radius-md；聚焦 box-shadow: var(--focus-ring) 外发光
 *   - 禁用态 --disabled-bg / --disabled-text（A-53 接线后的唯一口径）
 *
 * PrimeVue 4 的 Select 是「div.p-select + span.p-select-label + div.p-select-dropdown」
 * 的复合结构，高度必须落在根 div 上、垂直内边距必须从 label 上清掉，
 * 否则 34px 的外框会被 label 的 form.field.padding.y 撑开。故这里用 :deep() 覆盖内部段。
 *
 * 覆盖边界（有意为之）：只覆盖「输入框本体」；`.p-select-overlay` 选项面板由
 * appendTo 默认 teleport 到 body，scoped :deep() 够不到，继续沿用 style.css 的全局段
 * （那里已有 data-p-selected / data-p-focused 的选中态与键盘态）。
 *
 * ── 为什么是泛型组件（generic="T"）而不是 `value: unknown` ──
 * 早期签名是 `(e: 'update:modelValue', value: unknown)`，在 strictFunctionTypes 下
 * 参数是**逆变**的：`(val: string) => void` 不能赋给 `(value: unknown) => void`
 * （因为 unknown 可能塞进 number/object，string 处理不了），业务侧于是报
 * TS2322「(val: string) => void 不可赋给 (value: unknown) => any」。
 * 解法不是把参数改成 any（那只是把类型检查关掉），而是让 T 由 `modelValue` 推断：
 * 绑 `string` 就得到 `(value: string) => void`，绑 number 就得到 `(value: number) => void`。
 * 泛型只存在于编译期，运行时零开销；未绑定 modelValue 时 T 退化为 unknown（与旧行为一致）。
 *
 * bare 逃生舱：走 PrimeVue 官方 unstyled 模式（零基础视觉，不写任何清零字面量）。
 */
import Select from 'primevue/select'

defineOptions({ name: 'AppSelect', inheritAttrs: false })

type SelectSize = 'l' | 'm' | 's'

withDefaults(
  defineProps<{
    /** 受控值（v-model）；类型 T 由调用方绑定值推断，并原样回流给 update:modelValue */
    modelValue?: T
    /** 选项数组（原样透传给 Select） */
    options?: unknown[]
    /** 选项文案字段或取值函数 */
    optionLabel?: string | ((data: unknown) => string)
    /** 选项值字段或取值函数（不传则回传整个 option 对象） */
    optionValue?: string | ((data: unknown) => unknown)
    /** 多选 */
    multiple?: boolean
    /** 面板内过滤 */
    filter?: boolean
    /** 未选中时的占位文案 */
    placeholder?: string
    /** 尺寸档：l / m / s（默认 m） */
    size?: SelectSize
    disabled?: boolean
    invalid?: boolean
    /** 裸样式：不施加任何基础视觉 */
    bare?: boolean
  }>(),
  {
    // modelValue 刻意不进默认值表：T 可能是 string/number 等任意类型，
    // 给 undefined 以外的默认值会与 T 冲突（withDefaults 允许省略个别键）。
    options: () => [],
    optionLabel: undefined,
    optionValue: undefined,
    multiple: false,
    filter: false,
    placeholder: undefined,
    size: 'm',
    disabled: false,
    invalid: false,
    bare: false,
  },
)

const emit = defineEmits<{ (e: 'update:modelValue', value: T): void }>()

/**
 * 写值透传。PrimeVue 内部 emit 的是 any（它的 d_value 是运行时动态的），
 * 这里直接转成 T —— 类型责任在调用方（与 PrimeVue 自身的 modelValue: any 口径一致）。
 */
function onUpdate(value: T): void {
  emit('update:modelValue', value)
}
</script>

<template>
  <Select
    v-bind="$attrs"
    :model-value="modelValue"
    :options="options"
    :option-label="optionLabel"
    :option-value="optionValue"
    :multiple="multiple"
    :filter="filter"
    :placeholder="placeholder"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :class="bare
      ? ['app-select--bare']
      : ['app-select', `app-select--${size}`, { 'app-select--invalid': invalid, 'app-select--disabled': disabled }]"
    @update:model-value="onUpdate"
  />
</template>

<style scoped>
/* ── 基础外观：高度落在根 div（p-select 本身是 inline-flex），圆角/描边取令牌 ── */
.app-select {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  color: var(--text);
  transition: border-color var(--transition), box-shadow var(--transition), background-color var(--transition);
}

/* ── 尺寸档：清掉 label 的垂直内边距，让固定高度真正生效 ── */
.app-select--l {
  height: var(--input-height-lg);
}
.app-select--m {
  height: var(--input-height-md);
}
.app-select--s {
  height: var(--input-height-sm);
}

.app-select :deep(.p-select-label) {
  padding: 0 var(--space-14);
  font-size: var(--font-size-13);
  line-height: var(--line-height-none);
  color: var(--text);
}
.app-select--l :deep(.p-select-label) {
  padding: 0 var(--space-16);
  font-size: var(--font-size-15);
}
.app-select--s :deep(.p-select-label) {
  padding: 0 var(--space-12);
  font-size: var(--font-size-12);
}
.app-select :deep(.p-select-label.p-placeholder) {
  color: var(--text-dim);
}

/* 下拉箭头颜色跟随文字色，不单独设色 */
.app-select :deep(.p-select-dropdown) {
  color: var(--text-secondary);
}

/* ── 四态：hover / focus / invalid / disabled ── */
.app-select:not(.app-select--disabled):hover {
  border-color: var(--text-dim);
}
.app-select:not(.app-select--disabled).p-focus {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-select--invalid,
.app-select--invalid:not(.app-select--disabled):hover,
.app-select--invalid:not(.app-select--disabled).p-focus {
  border-color: var(--danger);
}

.app-select--disabled {
  background: var(--disabled-bg);
  border-color: var(--border);
  cursor: not-allowed;
}
.app-select--disabled :deep(.p-select-label),
.app-select--disabled :deep(.p-select-dropdown) {
  color: var(--disabled-text);
}
</style>
