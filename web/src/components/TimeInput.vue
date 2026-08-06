<template>
  <div class="time-input-group">
    <InputNumber
      v-model="hour"
      :min="0"
      :max="23"
      showButtons
      size="small"
      class="time-part"
      aria-label="小时"
    />
    <span class="time-separator">:</span>
    <InputNumber
      v-model="minute"
      :min="0"
      :max="59"
      showButtons
      size="small"
      class="time-part"
      aria-label="分钟"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'TimeInput' })
import { ref, watch } from 'vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const parseTime = (v: string) => {
  const [h = 3, m = 0] = (v || '03:00').split(':').map(Number)
  return [h, m] as const
}

const [initH, initM] = parseTime(props.modelValue)
const hour = ref(initH)
const minute = ref(initM)

// 子→父：值变化时同步
watch([hour, minute], () => {
  const h = String(hour.value).padStart(2, '0')
  const m = String(minute.value).padStart(2, '0')
  emit('update:modelValue', `${h}:${m}`)
}, { immediate: true })

// 父→子：外部值变化时同步（防止父组件重置后子组件不同步）
watch(() => props.modelValue, (v) => {
  const [h, m] = parseTime(v)
  if (h !== hour.value) hour.value = h
  if (m !== minute.value) minute.value = m
})
</script>

<style scoped>
.time-input-group {
  display: flex;
  gap: 4px;
  align-items: center;
}
.time-part {
  width: 64px;
}
.time-separator {
  font-weight: bold;
  color: var(--text-dim);
  padding: 0 2px;
}
</style>
