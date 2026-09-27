<script setup lang="ts">
/**
 * SettingsTabValidity — 时效性检查 + 熔断配置 Tab
 * Q16: 熔断配置已从独立 Tab 合并至此
 */
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import ValidityConfig from '@/components/ValidityConfig.vue'
import http from '@/api/http'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'

defineOptions({ name: 'SettingsTabValidity' })

const { t } = useI18n()

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
    circuitErr.value = t('settings.circuit.load_failed')
  }
}

function validateDurations(): string | null {
  const d = circuitCfg.value.freeze_durations
  for (let i = 0; i < d.length; i++) {
    if (!d[i] || d[i] < 1) return t('settings.circuit.err_step_min', { step: i + 1 })
    if (i > 0 && d[i] <= d[i - 1]) return t('settings.circuit.err_step_order')
  }
  if (circuitCfg.value.failure_threshold < 1) return t('settings.circuit.err_threshold')
  if (circuitCfg.value.reset_window_hours < 1) return t('settings.circuit.err_window')
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
    circuitErr.value = e.response?.data?.error || t('settings.circuit.save_failed')
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
      <span class="collapsible-title">{{ t('settings.validity.title') }}</span>
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
      <span class="collapsible-title">{{ t('settings.circuit.title') }}</span>
      <i :class="sections.circuit ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="sections.circuit" class="collapsible-content">
        <p class="text-dim mb-2">{{ t('settings.circuit.desc') }}</p>
        <Message v-if="circuitErr" severity="error" :closable="false">{{ circuitErr }}</Message>
        <Message v-if="circuitSaved" severity="success" :closable="false">{{ t('settings.saved') }}</Message>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fill, minmax(220px, 1fr))">
          <div style="display:flex;flex-direction:column;gap:6px">
            <label>{{ t('settings.circuit.failure_threshold') }}</label>
            <InputNumber v-model="circuitCfg.failure_threshold" :min="1" show-buttons />
          </div>
          <div v-for="i in 4" :key="i" style="display:flex;flex-direction:column;gap:6px">
            <label>{{ t('settings.circuit.step_duration', { step: i }) }}</label>
            <InputNumber v-model="circuitCfg.freeze_durations[i - 1]" :min="1" show-buttons />
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <label>{{ t('settings.circuit.reset_window') }}</label>
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
