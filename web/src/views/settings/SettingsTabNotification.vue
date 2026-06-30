<script setup lang="ts">
/**
 * SettingsTabNotification — 通知配置 Tab
 * 包装已有的 NotificationConfig + WechatTrustIP 组件。
 * 暴露 saveConfig 供父组件"应用"按钮调用。
 */
import { ref } from 'vue'
import NotificationConfig from '@/components/NotificationConfig.vue'
import WechatTrustIP from '@/components/WechatTrustIP.vue'

defineOptions({ name: 'SettingsTabNotification' })

const notificationRef = ref<InstanceType<typeof NotificationConfig> | null>(null)

// 暴露给父组件
defineExpose({ saveConfig: () => notificationRef.value?.saveConfig() })
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">通知配置</div>
    <NotificationConfig ref="notificationRef" />
    <hr style="margin:24px 0;border-color:var(--border)" />
    <div class="card-header" style="margin-bottom:12px">企业微信可信 IP 自动更新</div>
    <WechatTrustIP />
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
