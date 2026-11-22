<script setup lang="ts" generic="T extends boolean | string = boolean">
/**
 * AppToggle — 跨端设计系统（DS）开关（阶段二 · 模块一骨架）。
 *
 * 规则来源：docs/reference/ui-system.md「表单输入控件」
 *   - 三档尺寸：l / m / s（默认 m，等于 Aura 默认 40×24，迁移零视觉变化）
 *   - 轨道圆角取 --ds-radius-pill（开关天然胶囊形，不跟输入框的 md）
 *   - 开：轨道 --primary-fill；关：轨道 --border-light；滑块 --surface
 *   - 禁用：轨道 --disabled-bg、滑块 --disabled-text（A-53 接线后的唯一口径）
 *   - 聚焦统一 box-shadow: var(--focus-ring) 外发光（落在轨道上）
 *
 * 为什么包装 ToggleSwitch 而不是 Checkbox：语义不同（role=switch vs checkbox），
 * 且 ToggleSwitch 的 v-model 是 trueValue/falseValue 映射，不能靠 attrs 猜。
 *
 * ── 为什么是泛型组件（generic="T"）──
 * 早期签名是 `(e: 'update:modelValue', value: boolean | string)`，strictFunctionTypes 下
 * 参数逆变：`(val: boolean) => void` 不能赋给 `(value: boolean | string) => void`
 * （联合里的 string 分支 boolean 处理不了），业务侧于是报
 * TS2322「(val: boolean) => void 不可赋给 (value: string | boolean) => any」。
 * 让 T 由 `modelValue` 推断（boolean 绑定 → `(value: boolean) => void`；
 * 配 trueValue/falseValue 用字符串时 → `(value: string) => void`）即可根治。
 * 泛型只存在于编译期，运行时零开销。
 *
 * bare 逃生舱：走 PrimeVue 官方 unstyled 模式（零基础视觉，不写清零字面量）。
 */
import ToggleSwitch from 'primevue/toggleswitch'

defineOptions({ name: 'AppToggle', inheritAttrs: false })

type ToggleSize = 'l' | 'm' | 's'

withDefaults(
  defineProps<{
    /** 受控值（v-model）；类型 T 由绑定值推断（默认 boolean）；
     *  trueValue/falseValue 经 $attrs 透传 */
    modelValue?: T
    /** 尺寸档：l / m / s（默认 m） */
    size?: ToggleSize
    disabled?: boolean
    invalid?: boolean
    /** 裸样式：不施加任何基础视觉 */
    bare?: boolean
  }>(),
  {
    // modelValue 刻意不进默认值表：T 是泛型，给字面量默认值会与 T 冲突
    // （withDefaults 允许省略个别键；未传时由 PrimeVue 侧按 undefined 处理）。
    size: 'm',
    disabled: false,
    invalid: false,
    bare: false,
  },
)

const emit = defineEmits<{ (e: 'update:modelValue', value: T): void }>()

/**
 * 写值透传。
 * 注意形参必须声明为 `boolean`（而不是 T）：PrimeVue ToggleSwitch 的
 * `update:modelValue` 签名固定是 `(value: boolean) => void`，模板里的 handler
 * 必须能接受 boolean 才通得过类型检查。运行时它给的就是 trueValue/falseValue
 * （可能是字符串），故这里 `as T` 转一次——类型责任在调用方，与 PrimeVue
 * 自身 `modelValue: any` 的口径一致。
 */
function onUpdate(value: boolean): void {
  emit('update:modelValue', value as T)
}
</script>

<template>
  <ToggleSwitch
    v-bind="$attrs"
    :model-value="modelValue"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :class="bare
      ? ['app-toggle--bare']
      : ['app-toggle', `app-toggle--${size}`, { 'app-toggle--invalid': invalid }]"
    @update:model-value="onUpdate"
  />
</template>

<style scoped>
/* ── 尺寸档：轨道宽高与滑块直径三档联动（m 档 = Aura 默认 40×24 / 16）
     轨道宽度取 --space-* 的像素档：尺度层没有 32/40/44 的 --size-* 档，
     而开关是固定比例控件（宽:高 ≈ 5:3），不宜为它单独扩 --size-* 家族。 ── */
.app-toggle {
  --app-toggle-w: var(--space-40);
  --app-toggle-h: var(--size-24);
  --app-toggle-knob: var(--size-16);
}
.app-toggle--l {
  --app-toggle-w: var(--space-44);
  --app-toggle-h: var(--size-24);
  --app-toggle-knob: var(--size-20);
}
.app-toggle--s {
  --app-toggle-w: var(--space-32);
  --app-toggle-h: var(--size-20);
  --app-toggle-knob: var(--size-14);
}

.app-toggle {
  width: var(--app-toggle-w);
  height: var(--app-toggle-h);
}

/* ── 轨道：关态 --border-light，开态 --primary-fill；圆角取胶囊 ── */
.app-toggle :deep(.p-toggleswitch-slider) {
  background: var(--border-light);
  border-color: var(--border);
  border-radius: var(--ds-radius-pill);
}
.app-toggle.p-toggleswitch-checked :deep(.p-toggleswitch-slider) {
  background: var(--primary-fill);
  border-color: var(--primary-fill);
}

/* ── 滑块：底色 --surface（开/关同色，靠轨道区分状态） ── */
.app-toggle :deep(.p-toggleswitch-handle) {
  width: var(--app-toggle-knob);
  height: var(--app-toggle-knob);
  background: var(--surface);
  color: var(--text-secondary);
}

/* ── 四态：hover / focus / invalid / disabled ── */
.app-toggle:not(.p-disabled):hover :deep(.p-toggleswitch-slider) {
  border-color: var(--text-dim);
}
.app-toggle:not(.p-disabled):has(:focus-visible) :deep(.p-toggleswitch-slider) {
  box-shadow: var(--focus-ring);
}
.app-toggle--invalid :deep(.p-toggleswitch-slider) {
  border-color: var(--danger);
}

/* 禁用：轨道 --disabled-bg、滑块 --disabled-text（A-53 接线后的唯一口径） */
.app-toggle.p-disabled :deep(.p-toggleswitch-slider),
.app-toggle.p-disabled.p-toggleswitch-checked :deep(.p-toggleswitch-slider) {
  background: var(--disabled-bg);
  border-color: var(--border);
}
.app-toggle.p-disabled :deep(.p-toggleswitch-handle) {
  background: var(--disabled-text);
  color: var(--disabled-bg);
}
</style>
