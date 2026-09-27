<script setup lang="ts">
defineOptions({ name: 'QualityView' })
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Divider from 'primevue/divider'
import { runQualityCheck } from '@/api/quality'

const { t } = useI18n()
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
    console.error('质量检查失败:', e) // i18n-allow: 开发者日志：质量检查失败
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">{{ t('quality.title') }}</h2>
    <Card>
      <template #content>
        <div class="flex gap-3 align-items-center">
          <Button :label="t('quality.run')" icon="pi pi-play" @click="runCheck" :loading="running" />
          <span v-if="lastRun" class="text-sm">{{ t('quality.last_run', { time: formatTime(lastRun) }) }}</span>
        </div>

        <div v-if="results.length > 0">
          <Divider />
          <h4>{{ t('quality.summary', { failed: summary.failed, files: summary.files_checked }) }}</h4>
          <DataTable :value="results" striped-rows size="small">
            <Column field="rule" :header="t('quality.col_rule')" />
            <Column field="file" :header="t('quality.col_file')" />
            <Column field="line" :header="t('quality.col_line')" />
            <Column :header="t('quality.col_level')">
              <template #body="{ data }">
                <Tag :value="data.severity" :severity="data.severity === 'error' ? 'danger' : 'warn'" />
              </template>
            </Column>
            <Column field="message" :header="t('quality.col_message')" />
          </DataTable>
        </div>

        <div v-else-if="!running" class="text-center p-4" style="color: var(--text-color-secondary)">
          {{ t('quality.empty_hint') }}
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
