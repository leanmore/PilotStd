<script setup lang="ts">
/**
 * AppButton — 跨端设计系统（DS）统一按钮（阶段一骨架）。
 *
 * 规则来源：docs/reference/ui-system.md
 *   - 四种层级：primary / secondary / danger / ghost（语义互斥，不自创第五种）
 *   - 三档尺寸：l / m / s（高度取 --btn-height-*，不复用 --space-*）
 *   - 全部样式值来自 design-tokens.css，组件内不写字面量
 *
 * 门禁：业务代码禁止直接用原生 <button> 或 PrimeVue <Button>（custom/no-raw-button）。
 */
import { computed } from 'vue'

defineOptions({ name: 'AppButton' })

type ButtonType = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'l' | 'm' | 's'

const props = withDefaults(
  defineProps<{
    /** 层级：主操作 / 次操作 / 危险 / 幽灵 */
    type?: ButtonType
    /** 尺寸档 */
    size?: ButtonSize
    /** 文案（也可用默认插槽） */
    label?: string
    /** PrimeIcons 类名，如 `pi pi-check` */
    icon?: string
    /** 加载态：禁用点击并显示转圈 */
    loading?: boolean
    disabled?: boolean
    /** 撑满父容器宽度 */
    block?: boolean
  }>(),
  {
    type: 'secondary',
    size: 'm',
    label: '',
    icon: '',
    loading: false,
    disabled: false,
    block: false,
  },
)

const emit = defineEmits<{ (e: 'click', ev: MouseEvent): void }>()

const isInert = computed(() => props.disabled || props.loading)

function onClick(ev: MouseEvent): void {
  if (isInert.value) return
  emit('click', ev)
}
</script>

<template>
  <button
    type="button"
    class="app-btn"
    :class="[`app-btn--${type}`, `app-btn--${size}`, { 'app-btn--block': block, 'app-btn--loading': loading }]"
    :disabled="isInert"
    :aria-busy="loading ? 'true' : undefined"
    @click="onClick"
  >
    <i v-if="loading" class="pi pi-spin pi-spinner app-btn__icon" aria-hidden="true" />
    <i v-else-if="icon" :class="[icon, 'app-btn__icon']" aria-hidden="true" />
    <span v-if="label || $slots.default" class="app-btn__label">
      <slot>{{ label }}</slot>
    </span>
  </button>
</template>

<style scoped>
.app-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-8);
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-none);
  border-radius: var(--ds-radius-md);
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

/* ── 尺寸档：高度取 --btn-height-*，水平内边距取 --space-* ── */
.app-btn--l {
  height: var(--btn-height-lg);
  padding: 0 var(--space-20);
  font-size: var(--font-size-15);
}
.app-btn--m {
  height: var(--btn-height-md);
  padding: 0 var(--space-16);
  font-size: var(--font-size-13);
}
.app-btn--s {
  height: var(--btn-height-sm);
  padding: 0 var(--space-12);
  font-size: var(--font-size-12);
}

.app-btn--block {
  width: 100%;
}

/* ── 层级：Primary ── */
.app-btn--primary {
  background: var(--primary-fill);
  color: var(--text-on-primary);
}
.app-btn--primary:hover:not(:disabled) {
  background: var(--primary-fill-hover);
}

/* ── 层级：Secondary ── */
.app-btn--secondary {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
}
.app-btn--secondary:hover:not(:disabled) {
  background: var(--surface-raised);
}

/* ── 层级：Danger ── */
.app-btn--danger {
  background: var(--danger);
  color: var(--text-on-primary);
}
.app-btn--danger:hover:not(:disabled) {
  background: var(--danger-text);
}

/* ── 层级：Ghost ── */
.app-btn--ghost {
  background: transparent;
  color: var(--text-secondary);
}
.app-btn--ghost:hover:not(:disabled) {
  background: var(--surface-raised);
  color: var(--text);
}

/* ── 禁用 / 聚焦 ── */
.app-btn:disabled {
  /* 禁用态用已定义令牌：--disabled-bg/--disabled-text 目前是死键（A-53），
     接线后可直接替换为它们，不影响其它规则。 */
  background: var(--border-light);
  color: var(--text-dim);
  border-color: transparent;
  cursor: not-allowed;
}
.app-btn:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}

/* ── 图标 ── */
.app-btn__icon {
  font-size: var(--size-16);
  line-height: var(--line-height-none);
}
.app-btn--s .app-btn__icon {
  font-size: var(--size-14);
}
.app-btn--l .app-btn__icon {
  font-size: var(--size-20);
}
</style>
