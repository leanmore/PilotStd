<template>
  <div class="unified-filter-bar">
    <div
      v-for="type in types"
      :key="type.key"
      class="filter-item"
      :class="{ active: currentTab === type.key }"
      @click="$emit('update:currentTab', type.key)"
    >
      <span class="item-label">{{ type.label }}</span>
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
import ToggleSwitch from 'primevue/toggleswitch'

const props = defineProps<{
  currentTab: string
  fetchEnabled: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'update:currentTab', value: string): void
  (e: 'update:fetchEnabled', key: string, value: boolean): void
}>()

const types = [
  { key: 'gb', label: '国家标准公告' },
  { key: 'hb', label: '行业标准公告' },
  { key: 'db', label: '地方标准公告' },
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
  border-radius: 999px;
  padding: 4px;
  gap: 2px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  user-select: none;
}

.filter-item:hover {
  background: var(--primary-bg);
}

.filter-item.active {
  background: var(--primary);
}

.filter-item.active .item-label {
  color: #fff;
}

.item-label {
  font-size: 13px;
  color: var(--text-dim);
  white-space: nowrap;
}
</style>
