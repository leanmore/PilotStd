<template>
  <div class="unified-filter-bar">
    <div
      v-for="type in types"
      :key="type.key"
      class="filter-item"
      :class="{ active: currentTab === type.key }"
      @click="$emit('update:currentTab', type.key)"
    >
      <span class="item-label">{{ t(type.labelKey) }}</span>
      <div @click.stop>
        <ToggleSwitch
          :model-value="fetchEnabled[type.key]"
          @update:model-value="(val: boolean) => handleToggle(type.key, val)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'UnifiedFilterBar' })
import ToggleSwitch from 'primevue/toggleswitch'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  currentTab: string
  fetchEnabled: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'update:currentTab', value: string): void
  (e: 'update:fetchEnabled', key: string, value: boolean): void
}>()

const types = [
  { key: 'gb', labelKey: 'announce.type_long.gb' },
  { key: 'hb', labelKey: 'announce.type_long.hb' },
  { key: 'db', labelKey: 'announce.type_long.db' },
]

const handleToggle = (key: string, value: boolean) => {
  if (!value) {
    const enabledCount = Object.values(props.fetchEnabled).filter(Boolean).length
    if (enabledCount === 1 && props.fetchEnabled[key]) {
      return // 至少保留一个，不允许全关
    }
  }
  emit('update:fetchEnabled', key, value)
}
</script>

<style scoped>
.unified-filter-bar {
  display: inline-flex;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-pill);
  padding: var(--space-4);
  gap: var(--space-2);
}

.filter-item {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-6) var(--space-14);
  border-radius: var(--ds-radius-pill);
  cursor: pointer;
  transition: background-color 0.2s ease;
  user-select: none;
}

.filter-item:hover {
  background: var(--primary-bg);
}

.filter-item.active {
  background: var(--primary-fill);
}

.filter-item.active .item-label {
  /* TODO: [Design Debt] #fff 无精确令牌，暂不替换，待定令牌后统一处理 */
  color: #fff;
}

.item-label {
  font-size: var(--font-size-13);
  color: var(--text-dim);
  white-space: nowrap;
}
</style>
