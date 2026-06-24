<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputNumber from 'primevue/inputnumber'
import Tag from 'primevue/tag'
import Message from 'primevue/message'

// ── 适配器状态 ──
interface AdapterStatus {
  name: string
  status: string
  frozen_until: string | null
  remaining_seconds: number
  freeze_count: number
  fail_streak: number
}
const adapters = ref<AdapterStatus[]>([])
const statusErr = ref('')
const statusLoading = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

async function loadStatus() {
  statusLoading.value = true
  try {
    const r = await http.get('/adapter/status')
    adapters.value = r.data.adapters
    statusErr.value = ''
  } catch {
    statusErr.value = '加载适配器状态失败'
  } finally {
    statusLoading.value = false
  }
}

function tick() {
  let anyFrozen = false
  for (const a of adapters.value) {
    if (a.status === 'frozen' && a.remaining_seconds > 0) {
      a.remaining_seconds--
      anyFrozen = true
    }
  }
  // 所有适配器倒计时归零时自动刷
  if (!anyFrozen && adapters.value.some(a => a.status === 'frozen')) {
    loadStatus()
  }
}

function statusSeverity(s: string): 'success' | 'danger' | 'info' {
  if (s === 'frozen') return 'danger'
  if (s === 'normal') return 'success'
  return 'info'
}
function statusLabel(s: string): string {
  if (s === 'frozen') return '冻结中'
  if (s === 'normal') return '正常'
  return s
}

// ── 配置表单 ──
interface ConfigData {
  failure_threshold: number
  freeze_durations: number[]
  reset_window_hours: number
}
const config = ref<ConfigData>({ failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 })
const configErr = ref('')
const configSaved = ref(false)
const configLoading = ref(false)

async function loadConfig() {
  try {
    const r = await http.get('/adapter/config')
    config.value = r.data
    configErr.value = ''
  } catch {
    configErr.value = '加载配置失败'
  }
}

function validateDurations(): string | null {
  const d = config.value.freeze_durations
  for (let i = 0; i < d.length; i++) {
    if (!d[i] || d[i] < 1) return `第${i + 1}阶梯时长必须 >= 1`
    if (i > 0 && d[i] <= d[i - 1]) return '阶梯时长必须严格递增'
  }
  if (config.value.failure_threshold < 1) return '失败阈值必须 >= 1'
  if (config.value.reset_window_hours < 1) return '归零窗口必须 >= 1'
  return null
}

async function saveConfig() {
  const err = validateDurations()
  if (err) { configErr.value = err; return }
  configLoading.value = true
  configSaved.value = false
  try {
    await http.put('/adapter/config', config.value)
    configSaved.value = true
    configErr.value = ''
    await loadConfig()
    setTimeout(() => configSaved.value = false, 2000)
  } catch (e: any) {
    configErr.value = e.response?.data?.error || '保存配置失败'
  } finally {
    configLoading.value = false
  }
}

// ── 生命周期 ──
onMounted(() => {
  loadStatus()
  loadConfig()
  timer = setInterval(tick, 1000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="dashboard">
    <h2 class="page-title">适配器熔断监控</h2>

    <!-- 状态表格 -->
    <Card class="section">
      <template #title>
        <div class="card-header">
          <span>适配器状态</span>
          <Button
            icon="pi pi-refresh"
            label="刷新"
            size="small"
            severity="secondary"
            :loading="statusLoading"
            @click="loadStatus"
          />
        </div>
      </template>
      <template #content>
        <Message v-if="statusErr" severity="error" :closable="false">{{ statusErr }}</Message>
        <table class="adapter-table" v-if="adapters.length">
          <thead>
            <tr>
              <th>适配器</th>
              <th>状态</th>
              <th>剩余冻结</th>
              <th>冻结次数</th>
              <th>连续失败</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in adapters" :key="a.name">
              <td><strong>{{ a.name.toUpperCase() }}</strong></td>
              <td><Tag :severity="statusSeverity(a.status)" :value="statusLabel(a.status)" /></td>
              <td>{{ a.status === 'frozen' ? `${a.remaining_seconds}s` : '—' }}</td>
              <td>{{ a.freeze_count }}</td>
              <td>{{ a.fail_streak }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">暂无适配器数据</p>
      </template>
    </Card>

    <!-- 配置表单 -->
    <Card class="section">
      <template #title>熔断配置</template>
      <template #content>
        <Message v-if="configErr" severity="error" :closable="false">{{ configErr }}</Message>
        <Message v-if="configSaved" severity="success" :closable="false">配置已保存</Message>

        <div class="form-grid">
          <div class="field">
            <label>失败阈值</label>
            <InputNumber v-model="config.failure_threshold" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>第1阶梯时长 (分钟)</label>
            <InputNumber v-model="config.freeze_durations[0]" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>第2阶梯时长 (分钟)</label>
            <InputNumber v-model="config.freeze_durations[1]" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>第3阶梯时长 (分钟)</label>
            <InputNumber v-model="config.freeze_durations[2]" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>第4阶梯时长 (分钟)</label>
            <InputNumber v-model="config.freeze_durations[3]" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>归零窗口 (小时)</label>
            <InputNumber v-model="config.reset_window_hours" :min="1" show-buttons />
          </div>
        </div>

        <div class="form-actions">
          <Button
            icon="pi pi-save"
            label="保存配置"
            severity="primary"
            :loading="configLoading"
            @click="saveConfig"
          />
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 960px;
}
.page-title {
  margin: 0 0 20px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-heading);
}
.section {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.adapter-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.adapter-table th,
.adapter-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.adapter-table th {
  font-weight: 600;
  color: var(--text-dim);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.empty {
  color: var(--text-dim);
  font-size: 14px;
  padding: 20px 0;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-dim);
}
.form-actions {
  padding-top: 8px;
}
</style>
