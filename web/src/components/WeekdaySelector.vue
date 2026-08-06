<template>
  <div class="weekday-selector">
    <span class="weekday-prefix">周</span>
    <div
      class="weekday-display"
      tabindex="0"
      role="spinbutton"
      :aria-valuetext="'周' + weekDays[index]"
      @keydown="onKeydown"
    >
      {{ weekDays[index] }}
    </div>
    <div class="weekday-controls">
      <Button icon="pi pi-chevron-up" text size="small" @click="prev" aria-label="上一天" />
      <Button icon="pi pi-chevron-down" text size="small" @click="next" aria-label="下一天" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const DAYS = ['一', '二', '三', '四', '五', '六', '日'] as const
type DayLabel = typeof DAYS[number]

const props = defineProps<{ modelValue: DayLabel }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: DayLabel): void }>()

const initIndex = Math.max(0, DAYS.indexOf(props.modelValue || '二'))
const index = ref(initIndex)

const prev = () => { index.value = (index.value - 1 + 7) % 7 }
const next = () => { index.value = (index.value + 1) % 7 }

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowUp') { e.preventDefault(); prev() }
  else if (e.key === 'ArrowDown') { e.preventDefault(); next() }
}

// 子→父
watch(index, (v) => emit('update:modelValue', DAYS[v]), { immediate: true })

// 父→子
watch(() => props.modelValue, (v) => {
  const idx = DAYS.indexOf(v)
  if (idx >= 0 && idx !== index.value) index.value = idx
})

const weekDays = DAYS
</script>

<style scoped>
.weekday-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
}
.weekday-prefix {
  font-weight: 500;
  color: var(--text);
  font-size: 14px;
}
.weekday-display {
  width: 40px;
  text-align: center;
  font-size: 18px;
  font-weight: 600;
  padding: 4px 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  outline: none;
  cursor: default;
  transition: border-color 0.2s;
}
.weekday-display:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-100, color-mix(in srgb, var(--primary) 20%, transparent));
}
.weekday-controls {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.weekday-controls .p-button {
  width: 28px;
  height: 20px;
  padding: 0;
  font-size: 12px;
}
</style>
