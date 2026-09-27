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
  box-shadow: var(--shadow-xs); padding: 20px;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
}
.widget-header { font-weight: 700; color: var(--text-heading); font-size: 15px; margin-bottom: 8px; }
.empty-text { color: var(--text-dim); font-size: 13px; }
</style>
