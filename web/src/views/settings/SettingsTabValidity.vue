<script setup lang="ts">
/**
 * SettingsTabValidity — 时效性检查 Tab
 * 包装已有的 ValidityConfig 组件，折叠优化长页面。
 */
import { ref } from 'vue'
import ValidityConfig from '@/components/ValidityConfig.vue'

defineOptions({ name: 'SettingsTabValidity' })

const validityRef = ref<InstanceType<typeof ValidityConfig> | null>(null)
const sections = ref({ rules: true })

defineExpose({ doSave: () => validityRef.value?.doSave() })
</script>

<template>
  <div class="collapsible-card mt-2">
    <div class="collapsible-header" @click="sections.rules = !sections.rules">
      <span class="collapsible-title">时效性检查配置</span>
      <i :class="sections.rules ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="sections.rules" class="collapsible-content">
        <ValidityConfig ref="validityRef" />
      </div>
    </transition>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
