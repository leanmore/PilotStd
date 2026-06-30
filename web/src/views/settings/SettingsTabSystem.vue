<script setup lang="ts">
/**
 * SettingsTabSystem — 系统管理 Tab
 * 包含文件监控、缓存管理、任务管理三个可折叠区域。
 * 折叠状态通过 props 传入，支持双向绑定。
 */
import CacheManager from '@/components/CacheManager.vue'
import FileMonitor from '@/components/FileMonitor.vue'
import TaskManager from '@/components/TaskManager.vue'

defineOptions({ name: 'SettingsTabSystem' })

interface SystemSections {
  fileMonitor: boolean
  cacheManager: boolean
  taskManager: boolean
}

const props = defineProps<{
  sections: SystemSections
}>()

const emit = defineEmits<{
  (e: 'update:sections', value: SystemSections): void
}>()

function toggle(key: keyof SystemSections) {
  emit('update:sections', { ...props.sections, [key]: !props.sections[key] })
}
</script>

<template>
  <div class="mt-2 system-sections">
    <!-- 文件监控 -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="toggle('fileMonitor')">
        <span class="collapsible-title">文件监控</span>
        <i :class="sections.fileMonitor ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.fileMonitor" class="collapsible-content">
          <FileMonitor />
        </div>
      </transition>
    </div>

    <!-- 缓存管理 -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="toggle('cacheManager')">
        <span class="collapsible-title">缓存管理</span>
        <i :class="sections.cacheManager ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.cacheManager" class="collapsible-content">
          <CacheManager />
        </div>
      </transition>
    </div>

    <!-- 任务管理 -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="toggle('taskManager')">
        <span class="collapsible-title">任务管理</span>
        <i :class="sections.taskManager ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.taskManager" class="collapsible-content">
          <TaskManager />
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
