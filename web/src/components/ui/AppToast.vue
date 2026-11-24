<script setup lang="ts">
/**
 * AppToast — 跨端设计系统（DS）Toast 渲染宿主（阶段三 · 模块四）。
 *
 * 职责：**只负责渲染**，不暴露 add() API —— 调用侧统一走 `useAppToast()` / `appToast`
 * （见 `@/composables/useAppToast`，那里解释了为什么必须分成 composable + 宿主两件套）。
 *
 * 规则来源：docs/reference/ui-system.md §14.1（微交互规范）
 *   - 位置：右上角（`top-right`），与 DS 的"页面右上操作区"视线一致
 *   - 圆角：--ds-radius-md（与按钮/输入框/卡片同一口径）
 *   - 阴影：--shadow-md（浮层，需与内容明显分离）
 *   - 语义色：success/info/warn/error 与主题变量一一对应，不自创第五种
 *   - 停留时长：由 useAppToast 的 DEFAULT_LIFE 决定（success/info 2s、warn/error 3s）
 *
 * 为什么不用 PrimeVue 默认样式：Aura 的 Toast 是「白底 + 左侧细色条」，
 * 与 DS 的「实色语义底 + 白字」不是同一套语言（按钮/标签都是实色语义底）。
 * 这里用 `:pt` 覆盖到与 DS 一致，且所有值取令牌。
 */
import Toast from 'primevue/toast'

defineOptions({ name: 'AppToast' })

withDefaults(
  defineProps<{
    /** 出现位置（默认右上，与 DS 操作区视线一致） */
    position?:
      | 'top-right'
      | 'top-left'
      | 'top-center'
      | 'bottom-right'
      | 'bottom-left'
      | 'bottom-center'
      | 'center'
    /** 同时最多显示条数（超出后最早的自动出队） */
    limit?: number
  }>(),
  { position: 'top-right', limit: 5 },
)

/** severity → PrimeIcons 图标（纯函数，无响应式依赖） */
const SEVERITY_ICON: Record<string, string> = {
  success: 'pi pi-check-circle',
  info: 'pi pi-info-circle',
  warn: 'pi pi-exclamation-triangle',
  error: 'pi pi-times-circle',
}

function severityIcon(severity: string): string {
  return SEVERITY_ICON[severity] ?? 'pi pi-info-circle'
}
</script>

<template>
  <Toast
    :position="position"
    :pt="{
      root: { class: 'app-toast' },
      message: { class: 'app-toast__message' },
      messageContent: { class: 'app-toast__content' },
      summary: { class: 'app-toast__summary' },
      detail: { class: 'app-toast__detail' },
      closeButton: { class: 'app-toast__close' },
      icon: { class: 'app-toast__icon' },
    }"
  >
    <template #message="{ message }">
      <!-- 自定义消息体：语义图标 + 标题 + 明细，全部取令牌 -->
      <div class="app-toast__body" :class="`app-toast__body--${message.severity}`" role="status">
        <i :class="severityIcon(message.severity)" class="app-toast__icon" aria-hidden="true" />
        <div class="app-toast__text">
          <div class="app-toast__summary">{{ message.summary }}</div>
          <div v-if="message.detail" class="app-toast__detail">{{ message.detail }}</div>
        </div>
      </div>
    </template>
  </Toast>
</template>

<script lang="ts">
/** severity → PrimeIcons 图标已移到上方 setup 块内，此块仅保留给将来可能的 named exports。 */
export {}
</script>

<style>
/* 非 scoped：Toast 经 Portal 渲染到 body 下，scoped 的 [data-v-*] 落不到那些节点上
   （与 AppDialog / AppConfirmDialog 同一限制）。所有选择器以 .app-toast 前缀收口。 */

/* ── 消息卡片：实色语义底 + 白字，与 DS 的按钮/标签同一视觉语言 ── */
.app-toast__body {
  display: flex;
  align-items: flex-start;
  gap: var(--space-10);
  padding: var(--space-12) var(--space-16);
  border-radius: var(--ds-radius-md);
  box-shadow: var(--shadow-md);
  color: var(--text-on-primary);
  font-size: var(--font-size-13);
  line-height: var(--line-height-compact);
  min-width: 240px;
  max-width: 420px;
}

.app-toast__body--success {
  background: var(--success);
}
.app-toast__body--info {
  background: var(--info);
}
.app-toast__body--warn {
  background: var(--warn-text);
}
.app-toast__body--error {
  background: var(--danger);
}

.app-toast__icon {
  font-size: var(--size-16);
  line-height: var(--line-height-snug);
  flex-shrink: 0;
}

.app-toast__text {
  min-width: 0;
  flex: 1;
}

.app-toast__summary {
  font-weight: var(--font-weight-medium);
  word-break: break-word;
}

.app-toast__detail {
  margin-top: var(--space-2);
  font-size: var(--font-size-12);
  opacity: 0.9;
  word-break: break-word;
}

/* ── 容器：去掉 PrimeVue 默认的卡片底/边框（我们的 body 已自带） ── */
.app-toast .p-toast-message {
  background: transparent;
  border: none;
  box-shadow: none;
  margin: 0 0 var(--space-8);
}

.app-toast .p-toast-message-content {
  padding: 0;
  border: none;
}

/* 关闭按钮：不显示（useAppToast 统一 closable:false），但保留样式以防调用方显式开启 */
.app-toast__close {
  color: var(--text-on-primary);
  opacity: 0.8;
}
.app-toast__close:hover {
  opacity: 1;
}

/* ── 进出场动画：从右侧滑入，与 DS 的 page 过渡时长一致（150ms） ── */
.app-toast .p-toast-message-enter-active {
  transition: transform 0.15s ease, opacity 0.15s ease;
}
.app-toast .p-toast-message-leave-active {
  transition: transform 0.15s ease, opacity 0.15s ease;
}
.app-toast .p-toast-message-enter-from,
.app-toast .p-toast-message-leave-to {
  transform: translateX(16px);
  opacity: 0;
}
</style>
