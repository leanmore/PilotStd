<script setup lang="ts">
/**
 * AppDatePicker — 跨端设计系统（DS）日期选择（阶段二 · 模块一骨架）。
 *
 * 规则来源：docs/reference/ui-system.md「表单输入控件」
 *   - 三档尺寸：l / m / s，输入框高度取 --input-height-*（语义独立于 --btn-height-*）
 *   - 圆角 --ds-radius-md；聚焦 box-shadow: var(--focus-ring) 外发光
 *   - 禁用态 --disabled-bg / --disabled-text（A-53 接线后的唯一口径）
 *
 * PrimeVue 4 的 DatePicker 结构是「span.p-datepicker + InputText.p-datepicker-input」：
 * 真正的输入框是内层 input，故描边/高度/内边距必须经 :deep(.p-datepicker-input) 落到它身上；
 * 外层 span 只做 inline-flex 排布，自己不画描边（避免与内层形成双层框）。
 * 面板（.p-datepicker-panel）默认 teleport 到 body，scoped :deep() 够不到，
 * 继续沿用 style.css 的全局段（那里已有 html 前缀的选中日覆盖）。
 *
 * 尺寸口径说明：DatePicker 的 size prop 在 PrimeVue 里只有 small/large 两档，
 * 与 DS 的 l/m/s 三档不同构，故不透传 size 给 PrimeVue，只用它选高度令牌。
 *
 * bare 逃生舱：走 PrimeVue 官方 unstyled 模式（零基础视觉）。
 */
import DatePicker from 'primevue/datepicker'

defineOptions({ name: 'AppDatePicker', inheritAttrs: false })

type DatePickerSize = 'l' | 'm' | 's'

withDefaults(
  defineProps<{
    /** 受控值（v-model）：单个 Date / 区间数组 / null；与 PrimeVue 签名保持一致 */
    modelValue?: Date | Array<Date | null> | null
    /** 尺寸档：l / m / s（默认 m） */
    size?: DatePickerSize
    disabled?: boolean
    invalid?: boolean
    /** 裸样式：不施加任何基础视觉 */
    bare?: boolean
  }>(),
  {
    modelValue: null,
    size: 'm',
    disabled: false,
    invalid: false,
    bare: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: Date | Array<Date | null> | null | undefined): void
}>()

function onUpdate(value: Date | Array<Date | null> | null | undefined): void {
  emit('update:modelValue', value)
}
</script>

<template>
  <DatePicker
    v-bind="$attrs"
    :model-value="modelValue"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :class="bare
      ? ['app-datepicker--bare']
      : ['app-datepicker', `app-datepicker--${size}`, { 'app-datepicker--invalid': invalid, 'app-datepicker--disabled': disabled }]"
    @update:model-value="onUpdate"
  />
</template>

<style scoped>
/* ── 外壳：只负责排布，描边交给内层 input（单层框，与 AppInput 同口径） ── */
.app-datepicker {
  display: inline-flex;
  align-items: center;
  color: var(--text);
}

/* ── 尺寸档：高度落在内层 input 上（p-datepicker-input 才是真正的输入框） ── */
.app-datepicker :deep(.p-datepicker-input) {
  height: var(--input-height-md);
  padding: 0 var(--space-14);
  font-size: var(--font-size-13);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  color: var(--text);
  transition: border-color var(--transition), box-shadow var(--transition), background-color var(--transition);
}
.app-datepicker--l :deep(.p-datepicker-input) {
  height: var(--input-height-lg);
  padding: 0 var(--space-16);
  font-size: var(--font-size-15);
}
.app-datepicker--s :deep(.p-datepicker-input) {
  height: var(--input-height-sm);
  padding: 0 var(--space-12);
  font-size: var(--font-size-12);
}
.app-datepicker :deep(.p-datepicker-input::placeholder) {
  color: var(--text-dim);
}

/* 下拉箭头：颜色跟随文字层级，不单独设色；与输入框共享圆角右半边 */
.app-datepicker :deep(.p-datepicker-dropdown) {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  border-start-end-radius: var(--ds-radius-md);
  border-end-end-radius: var(--ds-radius-md);
}

/* ── 四态：hover / focus / invalid / disabled ── */
.app-datepicker:not(.app-datepicker--disabled) :deep(.p-datepicker-input:enabled:hover) {
  border-color: var(--text-dim);
}
.app-datepicker:not(.app-datepicker--disabled) :deep(.p-datepicker-input:enabled:focus) {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-datepicker--invalid :deep(.p-datepicker-input) {
  border-color: var(--danger);
}

.app-datepicker--disabled :deep(.p-datepicker-input) {
  background: var(--disabled-bg);
  border-color: var(--border);
  color: var(--disabled-text);
  cursor: not-allowed;
}
.app-datepicker--disabled :deep(.p-datepicker-dropdown) {
  background: var(--disabled-bg);
  border-color: var(--border);
  color: var(--disabled-text);
}
</style>
