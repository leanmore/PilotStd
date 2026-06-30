<script setup lang="ts">
/**
 * SettingsTabCircuit — 熔断配置 Tab
 * 自包含：拥有自己的状态、API 调用、表单校验逻辑。
 * 通过 defineExpose 暴露 saveCircuitConfig 供父组件"应用"按钮调用。
 */
import { ref, onMounted } from 'vue'
import http from '@/api/http'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'

defineOptions({ name: 'SettingsTabCircuit' })

interface CircuitConfig {
  failure_threshold: number
  freeze_durations: number[]
  reset_window_hours: number
}

const circuitCfg = ref<CircuitConfig>({ failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 })
const circuitErr = ref('')
const circuitSaved = ref(false)
const circuitLoading = ref(false)

async function loadCircuitConfig() {
  try {
    const r = await http.get('/adapter/config')
    circuitCfg.value = r.data
    circuitErr.value = ''
  } catch {
    circuitErr.value = '加载配置失败'
  }
}

function validateDurations(): string | null {
  const d = circuitCfg.value.freeze_durations
  for (let i = 0; i < d.length; i++) {
    if (!d[i] || d[i] < 1) return `第${i + 1}阶梯时长必须 >= 1`
    if (i > 0 && d[i] <= d[i - 1]) return '阶梯时长必须严格递增'
  }
  if (circuitCfg.value.failure_threshold < 1) return '失败阈值必须 >= 1'
  if (circuitCfg.value.reset_window_hours < 1) return '归零窗口必须 >= 1'
  return null
}

async function saveCircuitConfig() {
  const err = validateDurations()
  if (err) { circuitErr.value = err; return }
  circuitLoading.value = true
  circuitSaved.value = false
  try {
    await http.put('/adapter/config', circuitCfg.value)
    circuitSaved.value = true
    circuitErr.value = ''
    await loadCircuitConfig()
    setTimeout(() => circuitSaved.value = false, 2000)
  } catch (e: any) {
    circuitErr.value = e.response?.data?.error || '保存配置失败'
  } finally {
    circuitLoading.value = false
  }
}

// 暴露给父组件，供"应用"按钮调用
defineExpose({ saveCircuitConfig })

onMounted(() => { loadCircuitConfig() })
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">熔断配置</div>
    <p class="text-dim mb-2">控制各站点适配器的熔断阈值、阶梯冻结时长和失败归零窗口。</p>
    <Message v-if="circuitErr" severity="error" :closable="false">{{ circuitErr }}</Message>
    <Message v-if="circuitSaved" severity="success" :closable="false">配置已保存</Message>
    <div class="form-grid" style="grid-template-columns:repeat(auto-fill, minmax(220px, 1fr))">
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>失败阈值</label>
        <InputNumber v-model="circuitCfg.failure_threshold" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第1阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[0]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第2阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[1]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第3阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[2]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第4阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[3]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>归零窗口 (小时)</label>
        <InputNumber v-model="circuitCfg.reset_window_hours" :min="1" show-buttons />
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
