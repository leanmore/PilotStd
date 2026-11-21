<script setup lang="ts">
defineOptions({ name: 'PlaceholderWidget' })
// PlaceholderWidget.vue — 未实现 Widget 的占位卡片
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{ widget: { config?: { title?: string } } }>()
</script>

<template>
  <div class="placeholder-widget">
    <div class="widget-header">{{ widget.config?.title || t('dashboard.placeholder.title') }}</div>
    <p class="empty-text">{{ t('dashboard.placeholder.in_dev') }}</p>
  </div>
</template>

<style scoped>
.placeholder-widget {
  height: 100%; box-sizing: border-box;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs); padding: var(--space-20);
  display: flex; flex-direction: column; justify-content: center; align-items: center;
}
.widget-header { font-weight: var(--font-weight-bold); color: var(--text-heading); font-size: var(--font-size-15); margin-bottom: var(--space-8); }
.empty-text { color: var(--text-dim); font-size: var(--font-size-13); }
</style>
