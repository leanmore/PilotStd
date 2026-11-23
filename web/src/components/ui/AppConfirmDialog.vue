<script setup lang="ts">
/**
 * AppConfirmDialog — 跨端设计系统（DS）确认弹窗宿主（阶段三 · 模块二）。
 *
 * ── 为什么不能直接用 AppDialog 替代 ──
 * `<ConfirmDialog>` 不是普通弹窗：它是 **PrimeVue ConfirmationService 的渲染宿主**。
 * 业务侧调用 `confirm.require({ message, header, icon, accept, reject })` 把确认请求
 * 推进服务队列，再由 `<ConfirmDialog />` 这个**单例**把队列头渲染成弹窗。
 * 它没有 `v-model:visible`、没有默认插槽 —— 换成 `<AppDialog>` 会直接切断
 * `confirm.require()` 的整条链路（弹窗永远不出现，且不会报错）。
 *
 * 因此本组件保留 ConfirmationService 契约，只在**视觉层**套用 DS 口径
 * （圆角 / 内边距 / 遮罩 / 按钮层级），使它与 AppDialog 观感一致。
 *
 * 规则来源：docs/reference/ui-system.md §12.2（弹窗规范）
 *   - 圆角 --ds-radius-lg、内边距与 AppDialog 同档（--space-18 / --space-20）
 *   - 遮罩沿用 PrimeVue 默认（light/green 0.4、dark/blue 0.6），不新增颜色令牌
 *   - 接受/拒绝按钮走 AppButton 层级：accept = primary、reject = ghost
 *
 * 门禁：业务代码禁止直接 import `primevue/confirmdialog`（custom/no-raw-table），
 * 本组件是该规则的唯一收口点（豁免见 eslint.config.js 的 App*.vue 规则）。
 */
import ConfirmDialog from 'primevue/confirmdialog'
import AppButton from '@/components/ui/AppButton.vue'

defineOptions({ name: 'AppConfirmDialog', inheritAttrs: false })
</script>

<template>
  <ConfirmDialog
    v-bind="$attrs"
    :pt="{
      // 关闭按钮（右上）与 AppDialog 同口径：只收敛图标字号，不改按钮盒尺寸，
      // 避免热区缩到 20px（< WCAG 2.5.8 的 24px 最小目标）
      closeButton: { class: 'app-confirm-dialog__close' },
      // 接受/拒绝按钮：套 AppButton 的层级视觉
      acceptButton: { class: 'app-confirm-dialog__accept' },
      rejectButton: { class: 'app-confirm-dialog__reject' },
    }"
  >
    <!-- 把 accept/reject 按钮的文案渲染权交回业务（i18n 由调用方的 confirm.require 提供），
         这里仅确保按钮本身带上 DS 层级 class，不改点击语义。 -->
    <template #container="{ message, acceptCallback, rejectCallback }">
      <div class="app-confirm-dialog" role="alertdialog" aria-modal="true">
        <div class="app-confirm-dialog__header">
          <i v-if="message.icon" :class="message.icon" aria-hidden="true" />
          <span class="app-confirm-dialog__title">{{ message.header }}</span>
        </div>
        <div class="app-confirm-dialog__content">
          <p class="app-confirm-dialog__message">{{ message.message }}</p>
        </div>
        <div class="app-confirm-dialog__footer">
          <AppButton
            :label="message.rejectProps?.label"
            size="m"
            type="ghost"
            @click="rejectCallback"
          />
          <AppButton
            :label="message.acceptProps?.label"
            size="m"
            :type="message.acceptProps?.severity === 'danger' ? 'danger' : 'primary'"
            @click="acceptCallback"
          />
        </div>
      </div>
    </template>
  </ConfirmDialog>
</template>

<style>
/* 非 scoped：ConfirmDialog 经 Portal 渲染，内容不在本组件的 DOM 子树里，
   scoped 的 [data-v-*] 属性落不到那些节点上（与 AppDialog 同一限制，见其文件头注释）。
   所有选择器都以 .app-confirm-dialog 前缀收口，不污染全局 .p-confirmdialog。 */
.app-confirm-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-18) var(--space-20);
  min-width: 320px;
  max-width: 480px;
}

.app-confirm-dialog__header {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  margin-bottom: var(--space-12);
  color: var(--text-heading);
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-15);
}

.app-confirm-dialog__header i {
  font-size: var(--size-20);
  color: var(--warning);
}

.app-confirm-dialog__message {
  margin: 0;
  color: var(--text);
  font-size: var(--font-size-13);
  line-height: var(--line-height-body);
}

.app-confirm-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-8);
  margin-top: var(--space-20);
}

/* 关闭按钮：只收敛图标字号，保留 Aura 的按钮盒与热区（见上方 pt 注释） */
.app-confirm-dialog__close .p-dialog-close-button,
.app-confirm-dialog__close {
  font-size: var(--size-20);
}
</style>
