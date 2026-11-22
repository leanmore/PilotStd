<!-- #40 增量加载底部状态指示器（终版：含"加载全部"按钮） -->
<script setup lang="ts">
defineOptions({ name: 'TableLoadFooter' })

import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  displayed: number
  total: number
  isLoading: boolean
  showLoadAllButton: boolean
}>()

defineEmits<{
  loadAll: []
}>()
</script>

<template>
  <div v-if="total > 0" class="table-load-footer">
    <div v-if="isLoading" class="footer-row">
      <span class="spinner" />
      <span>{{ t('table_load.more') }}</span>
    </div>
    <div v-else-if="displayed >= total" class="footer-row footer-complete">
      {{ t('table_load.all_shown', { total }) }}
    </div>
    <div v-else-if="showLoadAllButton" class="footer-row">
      <span class="partial-text">{{ t('table_load.shown_partial', { displayed, total }) }}</span>
      <button class="load-all-btn" @click="$emit('loadAll')">
        {{ t('table_load.load_rest', { n: total - displayed }) }}
      </button>
    </div>
    <div v-else class="footer-row footer-hint">
      {{ t('table_load.scroll_hint', { displayed, total }) }}
    </div>
  </div>
</template>

<style scoped>
.table-load-footer {
  padding: var(--space-12) var(--space-16);
  text-align: center;
  font-size: var(--font-size-13);
  color: var(--text-dim);
  border-top: 1px solid var(--border);
}
.footer-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-10);
}
.load-all-btn {
  padding: var(--space-4) var(--space-12);
  border: 1px solid var(--primary);
  background: transparent;
  color: var(--primary);
  border-radius: var(--ds-radius-xs);
  cursor: pointer;
  font-size: var(--font-size-12);
  transition: all 0.2s;
}
.load-all-btn:hover {
  background: var(--primary-fill);
  color: var(--text-on-primary);
}
.partial-text {
  /* TODO: [Design Debt] #ca8a04 无精确令牌，暂不替换，待定令牌后统一处理 */
  color: #ca8a04;
}
.spinner {
  /* TODO: [Design Debt] 20px 无精确令牌，暂不替换，待定令牌后统一处理 */
  width: var(--size-20); height: var(--size-20);
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
