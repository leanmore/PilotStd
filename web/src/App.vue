<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import AppLayout from '@/components/AppLayout.vue'
import { useThemeSync } from '@/composables/useThemeSync'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const store = useAppStore()

useThemeSync()

// 已登录时从后端加载持久化配置（主题/语言）
onMounted(() => {
  if (route.path !== '/login') {
    store.loadPreferences()
  }
})
</script>

<template>
  <Toast position="bottom-right" />
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
