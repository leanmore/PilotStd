<script setup lang="ts">
/**
 * SettingsTabValidity — 时效性检查 + 熔断配置 Tab
 * Q16: 熔断配置已从独立 Tab 合并至此
 */
import { ref, onMounted } from 'vue'
import ValidityConfig from '@/components/ValidityConfig.vue'
import http from '@/api/http'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'

defineOptions({ name: 'SettingsTabValidity' })

const validityRef = ref<InstanceType<typeof ValidityConfig> | null>(null)
const sections = ref({ rules: true, circuit: true })

// ── 熔断配置（Q16: 从 SettingsTabCircuit 迁移）──
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
    const r = await http.get('/adapter/config', { routeTag: '/settings' })
    if (!r || !r.data) return  // 请求被取消（响应拦截器静默返回 null），不显示错误
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
  circuitLoading.value = true; circuitSaved.value = false
  try {
    await http.put('/adapter/config', circuitCfg.value)
    circuitSaved.value = true; circuitErr.value = ''
    await loadCircuitConfig()
    setTimeout(() => circuitSaved.value = false, 2000)
  } catch (e: any) {
    circuitErr.value = e.response?.data?.error || '保存配置失败'
  } finally {
    circuitLoading.value = false
  }
}

defineExpose({ doSave: () => validityRef.value?.doSave(), saveCircuitConfig })
onMounted(() => { loadCircuitConfig() })
</script>

<template>
  <!-- 时效性检查 -->
  <div class="collapsible-card mt-2">
    <div class="collapsible-header" @click="sections.rules = !sections.rules">
      <span class="collapsible-title">时效性检查配置</span>
      <i :class="sections.rules ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="sections.rules" class="collapsible-content">
        <ValidityConfig ref="validityRef" />
      </div>
    </transition>
  </div>

  <!-- Q16: 熔断配置（从独立Tab合并） -->
  <div class="collapsible-card mt-2">
    <div class="collapsible-header" @click="sections.circuit = !sections.circuit">
      <span class="collapsible-title">熔断配置</span>
      <i :class="sections.circuit ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="sections.circuit" class="collapsible-content">
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
    </transition>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
