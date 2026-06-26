<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'
import { useThemeSync } from '@/composables/useThemeSync'

const route = useRoute()

// 同步应用主题与 PrimeVue 主题状态
useThemeSync()
</script>

<template>
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
