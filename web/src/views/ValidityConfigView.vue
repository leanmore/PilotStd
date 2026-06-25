<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import { getValidityConfig, putValidityConfig, runValidityCheck, getValidityHistory, type ValidityConfig, type ValidityHistoryItem } from '@/api/validity'

const config = ref<ValidityConfig>({
  frequency: 'weekly', execute_time: '03:00', batch_size: 50,
  batch_interval: 5, check_ratio: 25, update_interval: 28,
})
const history = ref<ValidityHistoryItem[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)

const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const saved = ref(false)
const runResult = ref('')
const errMsg = ref('')

const freqOptions = [
  { label: '每日', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '每月', value: 'monthly' },
]

async function loadConfig() {
  try {
    config.value = await getValidityConfig()
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '加载配置失败'
  }
}

async function loadHistory() {
  try {
    const r = await getValidityHistory({ page: historyPage.value, page_size: 10 })
    history.value = r.items
    historyTotal.value = r.total
  } catch { /* 历史非关键 */ }
}

async function saveConfig() {
  saving.value = true
  saved.value = false
  errMsg.value = ''
  try {
    await putValidityConfig(config.value)
    saved.value = true
    setTimeout(() => (saved.value = false), 2000)
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '保存失败'
  } finally {
    saving.value = false
  }
}

async function runCheck() {
  running.value = true
  runResult.value = ''
  try {
    const r = await runValidityCheck()
    runResult.value = `检查完成：检查 ${r.checked} 条，${r.changed} 条状态变更`
    loadHistory()
  } catch (e: any) {
    runResult.value = `执行失败: ${e.response?.data?.error || e.message}`
  } finally {
    running.value = false
    setTimeout(() => (runResult.value = ''), 6000)
  }
}

function onHistoryPage(p: number) {
  historyPage.value = p
  loadHistory()
}

const hTotalPages = () => Math.max(1, Math.ceil(historyTotal.value / 10))

onMounted(() => {
  loadConfig()
  loadHistory()
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">时效性检查配置</h2>

    <Card class="section">
      <template #title>检查策略</template>
      <template #content>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
        <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>
        <Message v-if="runResult" severity="info" :closable="false">{{ runResult }}</Message>

        <div class="form-grid">
          <div class="field">
            <label>检查频率</label>
            <Select v-model="config.frequency" :options="freqOptions" optionLabel="label" optionValue="value" />
          </div>
          <div class="field">
            <label>执行时间</label>
            <InputText v-model="config.execute_time" type="time" />
          </div>
          <div class="field">
            <label>单批大小（条/批）</label>
            <InputNumber v-model="config.batch_size" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>批间隔（秒）</label>
            <InputNumber v-model="config.batch_interval" :min="1" show-buttons />
          </div>
          <div class="field">
            <label>检查比例（%）</label>
            <InputNumber v-model="config.check_ratio" :min="1" :max="100" show-buttons />
          </div>
          <div class="field">
            <label>状态更新间隔（天）</label>
            <InputNumber v-model="config.update_interval" :min="1" show-buttons />
          </div>
        </div>

        <div class="form-actions">
          <Button icon="pi pi-play" label="立即执行一次" severity="secondary" :loading="running" @click="runCheck" />
          <Button icon="pi pi-save" label="保存配置" :loading="saving" @click="saveConfig" />
        </div>
      </template>
    </Card>

    <Card class="section">
      <template #title>最近执行记录</template>
      <template #content>
        <table class="data-table" v-if="history.length">
          <thead>
            <tr>
              <th>执行时间</th>
              <th>检查条数</th>
              <th>状态变更</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.check_date">
              <td>{{ h.check_date }}</td>
              <td>{{ h.checked_count }}</td>
              <td>{{ h.changed_count }}条</td>
              <td><Tag severity="success" value="完成" /></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">暂无执行记录</p>

        <div class="pagination" v-if="hTotalPages() > 1">
          <Button icon="pi pi-angle-left" size="small" severity="secondary" text :disabled="historyPage <= 1" @click="onHistoryPage(historyPage - 1)" />
          <span class="page-info">{{ historyPage }}/{{ hTotalPages() }}</span>
          <Button icon="pi pi-angle-right" size="small" severity="secondary" text :disabled="historyPage >= hTotalPages()" @click="onHistoryPage(historyPage + 1)" />
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 800px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.section { margin-bottom: 16px; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 16px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; font-weight: 500; color: var(--text-dim); }
.form-actions { display: flex; gap: 10px; padding-top: 8px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
.data-table th { font-weight: 600; color: var(--text-dim); font-size: 12px; text-transform: uppercase; }
.empty { color: var(--text-dim); font-size: 14px; padding: 20px 0; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 12px; }
.page-info { font-size: 13px; color: var(--text-dim); }
</style>
