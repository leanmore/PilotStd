<script setup lang="ts">
/**
 * SettingsTabSchedule — 定时任务 Tab
 * Q18: 包含文件监控卡片（从 SettingsTabSystem 迁移）
 */
import { ref } from 'vue'
import FileMonitor from '@/components/FileMonitor.vue'

defineOptions({ name: 'SettingsTabSchedule' })

const sections = ref({ fileMonitor: true })
</script>

<template>
  <div class="mt-2">
    <!-- Q18: 文件监控（从系统Tab迁移） -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="sections.fileMonitor = !sections.fileMonitor">
        <span class="collapsible-title">文件监控</span>
        <i :class="sections.fileMonitor ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.fileMonitor" class="collapsible-content">
          <FileMonitor />
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
