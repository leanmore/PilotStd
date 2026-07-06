<script setup lang="ts">
/**
 * SettingsTabSchema.vue — Schema 驱动的通用设置 Tab 渲染器。
 *
 * 用法：<SettingsTabSchema tab-key="storage" />
 *
 * 从注入的 settingsSchema 中获取该 Tab 的所有字段元数据，
 * 遍历渲染 DynamicSettingField。
 */
import DynamicSettingField from '@/components/DynamicSettingField.vue'

defineOptions({ name: 'SettingsTabSchema' })

const props = defineProps<{
  tabKey: string
}>()

// 从父组件注入的 Schema 映射表：tab → fields[]
import { inject } from 'vue'
const schemaTabs = inject<Record<string, any[]>>('settingsSchemaTabs', {})

import { computed } from 'vue'
const LABELS: Record<string, string> = {
  storage: '存储设置',
  network: '网络设置',
  query: '查询设置',
  scan: '扫描设置',
  ocr: 'OCR 设置',
}

const fields = computed(() => schemaTabs[props.tabKey] || [])
const headerLabel = computed(() => LABELS[props.tabKey] || props.tabKey)
</script>

<template>
  <div v-if="fields.length" class="card mt-2">
    <div class="card-header">{{ headerLabel }}</div>
    <div class="form-grid">
      <DynamicSettingField
        v-for="f in fields"
        :key="f.key"
        :field-key="f.key"
      />
    </div>
  </div>
</template>

<style scoped>
@import '@/views/settings/shared.css';
</style>
