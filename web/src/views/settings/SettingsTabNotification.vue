<script setup lang="ts">
/**
 * SettingsTabNotification — 通知配置 Tab
 * 包装已有的 NotificationConfig + WechatTrustIP 组件。
 * 暴露 saveConfig 供父组件"应用"按钮调用。
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import NotificationConfig from '@/components/NotificationConfig.vue'
import WechatTrustIP from '@/components/WechatTrustIP.vue'

defineOptions({ name: 'SettingsTabNotification' })

const { t } = useI18n()

const notificationRef = ref<InstanceType<typeof NotificationConfig> | null>(null)

// 暴露给父组件
defineExpose({ saveConfig: () => notificationRef.value?.saveConfig() })
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">{{ t('notification.settings.config_title') }}</div>
    <NotificationConfig ref="notificationRef" />
    <hr style="margin:24px 0;border-color:var(--border)" />
    <div class="card-header" style="margin-bottom:12px">{{ t('notification.settings.wechat_ip_title') }}</div>
    <WechatTrustIP />
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
