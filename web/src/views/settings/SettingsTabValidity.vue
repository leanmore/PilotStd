<script setup lang="ts">
/**
 * SettingsTabValidity — 时效性检查 Tab
 * 包装已有的 ValidityConfig 组件。
 * 暴露 doSave 供父组件"应用"按钮调用。
 */
import { ref } from 'vue'
import ValidityConfig from '@/components/ValidityConfig.vue'

defineOptions({ name: 'SettingsTabValidity' })

const validityRef = ref<InstanceType<typeof ValidityConfig> | null>(null)

// 暴露给父组件
defineExpose({ doSave: () => validityRef.value?.doSave() })
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">时效性检查</div>
    <ValidityConfig ref="validityRef" />
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
