<script setup lang="ts">
defineOptions({ name: 'App' })
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import AppLayout from '@/components/AppLayout.vue'
import { useThemeSync } from '@/composables/useThemeSync'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const store = useAppStore()

useThemeSync()

// 偏好数据由 app store 的 watch(loggedIn) 在登录成功后自动拉取；此处兜底调用幂等安全
onMounted(() => {
  store.loadPreferences()
})
</script>

<template>
  <Toast />
  <AppLayout v-if="route.path !== '/login'">
    <router-view v-slot="{ Component, route: routeParam }">
      <transition name="page">
        <component :is="Component" :key="routeParam.path" />
      </transition>
    </router-view>
  </AppLayout>
  <router-view v-else v-slot="{ Component, route: routeParam }">
    <transition name="page">
      <component :is="Component" :key="routeParam.path" />
    </transition>
  </router-view>
</template>

<style>
.page-enter-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.page-leave-active { transition: opacity 0.1s ease, transform 0.1s ease; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
