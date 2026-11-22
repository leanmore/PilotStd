<script setup lang="ts">
/**
 * AppCheckbox — 跨端设计系统（DS）复选框（阶段二 · 模块一骨架）。
 *
 * 规则来源：docs/reference/ui-system.md「表单输入控件」
 *   - 三档尺寸：l / m / s，方块边长取 --size-*（固定比例控件，不消费 --input-height-*）
 *   - 选中态取 --primary-fill / --text-on-primary；禁用态取 --disabled-bg / --disabled-text
 *   - 聚焦统一 box-shadow: var(--focus-ring) 外发光（落在方块上，不是透明 input 上）
 *
 * 圆角口径说明：外框（root）跟随 DS 统一口径 --ds-radius-md；内部方块因为只有
 * 14/20/24px 三档，用 md（8px）在 s 档会变成圆形，故方块单独取 --ds-radius-sm，
 * 与 ui-system.md §4.1「输入框 / 小按钮（S）→ --ds-radius-sm」一致。
 *
 * 用法：支持 PrimeVue 的两种 v-model 形态 ——
 *   - 布尔：`<AppCheckbox v-model="checked" binary />`
 *   - 多选数组：`<AppCheckbox v-model="list" value="a" />`（value 由 $attrs 透传）
 *
 * bare 逃生舱：走 PrimeVue 官方 unstyled 模式（零基础视觉，不写清零字面量）。
 */
import Checkbox from 'primevue/checkbox'

defineOptions({ name: 'AppCheckbox', inheritAttrs: false })

type CheckboxSize = 'l' | 'm' | 's'

withDefaults(
  defineProps<{
    /** 受控值：布尔（binary）或数组（多选组） */
    modelValue?: boolean | unknown[]
    /** 尺寸档：l / m / s（默认 m，等于 PrimeVue Aura 的默认方块，迁移零视觉变化） */
    size?: CheckboxSize
    disabled?: boolean
    invalid?: boolean
    /** 裸样式：不施加任何基础视觉 */
    bare?: boolean
  }>(),
  {
    modelValue: false,
    size: 'm',
    disabled: false,
    invalid: false,
    bare: false,
  },
)

const emit = defineEmits<{ (e: 'update:modelValue', value: boolean | unknown[]): void }>()

function onUpdate(value: boolean | unknown[]): void {
  emit('update:modelValue', value)
}
</script>

<template>
  <Checkbox
    v-bind="$attrs"
    :model-value="modelValue"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :class="bare
      ? ['app-checkbox--bare']
      : ['app-checkbox', `app-checkbox--${size}`, { 'app-checkbox--invalid': invalid }]"
    @update:model-value="onUpdate"
  />
</template>

<style scoped>
/* ── 外框：跟 DS 统一圆角口径（root 本身不画视觉，圆角只为契约一致） ── */
.app-checkbox {
  border-radius: var(--ds-radius-md);
}

/* ── 尺寸档：方块边长取 --size-*；m 档等于 Aura 默认 20px ── */
.app-checkbox {
  --app-checkbox-box: var(--size-20);
  --app-checkbox-icon: var(--size-14);
}
.app-checkbox--l {
  --app-checkbox-box: var(--size-24);
  --app-checkbox-icon: var(--size-16);
}
.app-checkbox--s {
  --app-checkbox-box: var(--size-16);
  --app-checkbox-icon: var(--size-12);
}

.app-checkbox :deep(.p-checkbox-box) {
  width: var(--app-checkbox-box);
  height: var(--app-checkbox-box);
  border-radius: var(--ds-radius-sm);
  border-color: var(--border);
  background: var(--surface);
}
.app-checkbox :deep(.p-checkbox-icon) {
  width: var(--app-checkbox-icon);
  height: var(--app-checkbox-icon);
  font-size: var(--app-checkbox-icon);
}

/* ── 选中态：底色取主色填充，勾选图标取主色上的对比色 ── */
.app-checkbox :deep(.p-checkbox-checked .p-checkbox-box) {
  background: var(--primary-fill);
  border-color: var(--primary-fill);
}
.app-checkbox :deep(.p-checkbox-checked .p-checkbox-icon) {
  color: var(--text-on-primary);
}

/* ── 四态：hover / focus / invalid / disabled ── */
.app-checkbox:not(.p-disabled):hover :deep(.p-checkbox-box) {
  border-color: var(--text-dim);
}
.app-checkbox:not(.p-disabled):has(:focus-visible) :deep(.p-checkbox-box) {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-checkbox--invalid :deep(.p-checkbox-box) {
  border-color: var(--danger);
}

/* 禁用：方块用 --disabled-bg，图标用 --disabled-text（A-53 接线后的唯一口径） */
.app-checkbox.p-disabled :deep(.p-checkbox-box) {
  background: var(--disabled-bg);
  border-color: var(--border);
}
.app-checkbox.p-disabled :deep(.p-checkbox-checked .p-checkbox-box) {
  background: var(--disabled-bg);
}
.app-checkbox.p-disabled :deep(.p-checkbox-icon) {
  color: var(--disabled-text);
}
</style>
