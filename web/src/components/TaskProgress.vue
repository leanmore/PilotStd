<script setup lang="ts">
defineOptions({ name: 'TaskProgress' })
defineProps<{ progress: number; label: string; detail: string }>()
</script>
<template>
  <div class="task-progress">
    <div class="task-header">{{ label }}</div>
    <ProgressBar :value="progress" />
    <div class="task-detail">{{ detail }}</div>
  </div>
</template>
<style scoped>
.task-progress { background: var(--surface); padding: 16px; border-radius: 8px;
  border: 1px solid var(--border); margin-bottom: 12px; }
.task-header { font-weight: bold; margin-bottom: 8px; }
.task-detail { color: var(--text); font-size: 12px; margin-top: 6px; opacity: 0.7; }
</style>
