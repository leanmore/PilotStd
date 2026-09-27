<script setup lang="ts">
/**
 * SettingsTabSchema.vue — Schema 驱动的通用设置 Tab 渲染器。
 */
import { inject, computed, unref } from 'vue'
import { useI18n } from 'vue-i18n'
import DynamicSettingField from '@/components/DynamicSettingField.vue'

defineOptions({ name: 'SettingsTabSchema' })

const { t } = useI18n()

const props = defineProps<{
  tabKey: string
}>()

// 从父组件注入的 Schema 映射表：tab → fields[]
const schemaTabsRaw = inject<any>('settingsSchemaTabs', {})
const schemaTabs = computed<Record<string, any[]>>(() => unref(schemaTabsRaw))

// 卡片标题：存 key、渲染期翻译（locale 切换后 computed 自动重算）
const LABEL_KEYS: Record<string, string> = {
  storage: 'settings.schema.storage',
  network: 'settings.schema.network',
  query: 'settings.schema.query',
  scan: 'settings.schema.scan',
  ocr: 'settings.schema.ocr',
}

const fields = computed(() => schemaTabs.value[props.tabKey] || [])
const headerLabel = computed(() => {
  const key = LABEL_KEYS[props.tabKey]
  return key ? t(key) : props.tabKey
})
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
