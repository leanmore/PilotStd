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
/* ── 外壳承担**唯一一层**边框/底色/圆角（与 AppInput 同口径）──
   修 2026-11-24（P0-1）：此前描边画在内层 input 上、下拉按钮又画了一层带右边框圆角的
   独立框，两者叠加后日历图标外围出现「胶囊」，而清除图标（×）没有 → 视觉不统一。
   现改为：外层一个框，input 与两个图标都在这一个框内，图标同色同尺寸。 */
.app-datepicker {
  display: inline-flex;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  color: var(--text);
  transition: border-color var(--transition), box-shadow var(--transition), background-color var(--transition);
}

/* ── 内层 input：不再自带边框/底色/圆角，只保留高度、内边距与字号 ── */
.app-datepicker :deep(.p-datepicker-input) {
  height: var(--input-height-md);
  padding: 0 var(--space-14);
  font-size: var(--font-size-13);
  background: transparent;
  border: 0;
  box-shadow: none;
  color: var(--text);
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

/* 下拉按钮：与外层同框，不再自画边框/底色；颜色与清除图标统一取 --text-secondary */
.app-datepicker :deep(.p-datepicker-dropdown) {
  background: transparent;
  border: 0;
  color: var(--text-secondary);
  padding: 0 var(--space-12);
}
/* 清除图标（×）与日历图标统一：同色同尺寸（两枚均为 14×14 SVG），靠外层 flex 居中 */
.app-datepicker :deep(.p-datepicker-clear-icon) {
  color: var(--text-secondary);
}

/* ── 四态：hover / focus / invalid / disabled（全部落在**外层**，因边框已上移）── */
.app-datepicker:not(.app-datepicker--disabled):hover {
  border-color: var(--text-dim);
}
.app-datepicker:not(.app-datepicker--disabled):focus-within {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-datepicker--invalid {
  border-color: var(--danger);
}
/* 内层 input 自己不再画 focus 环（否则会在框内再套一层） */
.app-datepicker :deep(.p-datepicker-input:enabled:focus) {
  box-shadow: none;
  outline: none;
}

.app-datepicker--disabled {
  background: var(--disabled-bg);
  border-color: var(--border);
}
.app-datepicker--disabled :deep(.p-datepicker-input) {
  color: var(--disabled-text);
  cursor: not-allowed;
}
.app-datepicker--disabled :deep(.p-datepicker-dropdown),
.app-datepicker--disabled :deep(.p-datepicker-clear-icon) {
  color: var(--disabled-text);
}
</style>
