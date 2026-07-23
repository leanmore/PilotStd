<script setup lang="ts">
/**
 * SettingsTabSystem — 系统管理 Tab
 * Q18: 文件监控已迁移至 SettingsTabSchedule
 * 包含缓存管理、任务管理两个可折叠区域。
 */
import CacheManager from '@/components/CacheManager.vue'
import TaskManager from '@/components/TaskManager.vue'

defineOptions({ name: 'SettingsTabSystem' })

interface SystemSections {
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

    <!-- 后台任务调度 -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="toggle('taskManager')">
        <span class="collapsible-title">后台任务调度</span>
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
