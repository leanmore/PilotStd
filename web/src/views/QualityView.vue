<script setup lang="ts">
defineOptions({ name: 'QualityView' })
import { ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Divider from 'primevue/divider'
import { runQualityCheck } from '@/api/quality'

const results = ref<any[]>([])
const summary = ref({ total: 0, files_checked: 0, passed: true, failed: 0 })
const running = ref(false)
const lastRun = ref<string | null>(null)

const formatTime = (iso: string) => new Date(iso).toLocaleString('zh-CN')

const runCheck = async () => {
  running.value = true
  try {
    const resp = await runQualityCheck({})
    const data = resp.data
    if (data.ok) {
      results.value = data.results || []
      summary.value = data.summary || { total: 0, files_checked: 0, passed: true, failed: 0 }
      lastRun.value = new Date().toISOString()
    }
  } catch (e) {
    console.error('质量检查失败:', e)
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">数据质量检查</h2>
    <Card>
      <template #content>
        <div class="flex gap-3 align-items-center">
          <Button label="运行检查" icon="pi pi-play" @click="runCheck" :loading="running" />
          <span v-if="lastRun" class="text-sm">上次检查: {{ formatTime(lastRun) }}</span>
        </div>

        <div v-if="results.length > 0">
          <Divider />
          <h4>检查结果 ({{ summary.failed }} 项违规 / {{ summary.files_checked }} 文件)</h4>
          <DataTable :value="results" striped-rows size="small">
            <Column field="rule" header="规则" />
            <Column field="file" header="文件" />
            <Column field="line" header="行" />
            <Column header="级别">
              <template #body="{ data }">
                <Tag :value="data.severity" :severity="data.severity === 'error' ? 'danger' : 'warn'" />
              </template>
            </Column>
            <Column field="message" header="信息" />
          </DataTable>
        </div>

        <div v-else-if="!running" class="text-center p-4" style="color: var(--text-color-secondary)">
          点击「运行检查」开始数据质量检查
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.flex { display: flex; }
.gap-3 { gap: 12px; }
.align-items-center { align-items: center; }
.text-sm { font-size: 13px; color: var(--text-color-secondary); }
.text-center { text-align: center; }
.p-4 { padding: 24px; }
h4 { margin: 12px 0 8px; font-size: 15px; }
</style>
