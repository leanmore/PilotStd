<script setup lang="ts">
/**
 * DownloadImport — Q24: 手动导入下载列表
 * 支持文本域输入标准号（一行一个）或上传 CSV/TXT 文件。
 */
defineOptions({ name: 'DownloadImport' })
import { ref } from 'vue'
import axios from 'axios'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

interface ImportResult {
  valid: string[]
  invalid: string[]
  duplicates: string[]
  total: number
  success: number
  failed: number
  skipped: number
  results: Array<{
    standard_number: string
    standard_name: string
    status: string
    saved_path: string
    error: string
  }>
}

const textInput = ref('')
const submitting = ref(false)
const result = ref<ImportResult | null>(null)
const showInvalid = ref(false)

function statusSeverity(status: string) {
  const map: Record<string, 'success' | 'danger' | 'warn' | 'info'> = {
    success: 'success', failed: 'danger', skipped: 'warn',
  }
  return map[status] || 'info'
}

async function handleSubmit() {
  if (!textInput.value.trim()) return
  submitting.value = true
  try {
    const form = new FormData()
    form.append('text', textInput.value)
    const { data } = await axios.post('/api/download/import', form)
    result.value = data as ImportResult
  } catch {
    result.value = null
  } finally {
    submitting.value = false
  }
}

function handleFileUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target?.result as string
    const lines = content.split('\n').map(l => l.trim()).filter(Boolean)
    if (textInput.value) textInput.value += '\n'
    textInput.value += lines.join('\n')
  }
  reader.readAsText(file)
  input.value = ''
}
</script>

<template>
  <div class="download-import">
    <h2>手动导入下载列表</h2>

    <Card class="mb-3">
      <template #content>
        <div class="input-area">
          <Textarea
            v-model="textInput"
            placeholder="每行输入一个标准号，如：&#10;GB/T 12345-2020&#10;ISO 9001:2015&#10;DB50/T 1982-2026"
            rows="8"
            class="w-full"
            :disabled="submitting"
          />
          <div class="file-upload mt-2">
            <input
              type="file"
              accept=".csv,.txt"
              @change="handleFileUpload"
              :disabled="submitting"
            />
            <span class="hint text-sm text-color-secondary">
              上传 CSV 或 TXT 文件，自动解析并追加到文本框
            </span>
          </div>
        </div>
      </template>
    </Card>

    <div class="actions mb-3">
      <Button
        label="提交下载"
        icon="pi pi-download"
        @click="handleSubmit"
        :loading="submitting"
        :disabled="!textInput.trim()"
      />
      <Button
        label="清空"
        icon="pi pi-times"
        severity="secondary"
        text
        @click="textInput = ''; result = null"
        class="ml-2"
      />
    </div>

    <div v-if="result" class="result-area">
      <!-- 统计卡片 -->
      <div class="stats flex gap-3 mb-3">
        <Card class="flex-1">
          <template #content>
            <div class="text-center">
              <div class="text-2xl font-bold text-primary">{{ result.valid.length }}</div>
              <div class="text-sm text-color-secondary">有效</div>
            </div>
          </template>
        </Card>
        <Card class="flex-1">
          <template #content>
            <div class="text-center">
              <div class="text-2xl font-bold" :class="result.invalid.length ? 'text-red-500' : 'text-color'">
                {{ result.invalid.length }}
              </div>
              <div class="text-sm text-color-secondary">无效</div>
            </div>
          </template>
        </Card>
        <Card class="flex-1">
          <template #content>
            <div class="text-center">
              <div class="text-2xl font-bold text-orange-500">{{ result.duplicates.length }}</div>
              <div class="text-sm text-color-secondary">重复</div>
            </div>
          </template>
        </Card>
      </div>

      <!-- 无效条目 -->
      <div v-if="result.invalid.length" class="mb-3">
        <Button
          :label="showInvalid ? '收起无效条目' : `查看无效条目 (${result.invalid.length})`"
          icon="pi pi-exclamation-triangle"
          severity="warn"
          text
          size="small"
          @click="showInvalid = !showInvalid"
        />
        <Card v-if="showInvalid" class="mt-2">
          <template #content>
            <ul class="invalid-list pl-3">
              <li v-for="item in result.invalid" :key="item" class="text-sm">{{ item }}</li>
            </ul>
          </template>
        </Card>
      </div>

      <!-- 下载结果 -->
      <Card v-if="result.results.length">
        <template #title>下载结果</template>
        <template #content>
          <DataTable :value="result.results" stripedRows size="small">
            <Column field="standard_number" header="标准号" style="min-width:12rem" />
            <Column field="standard_name" header="标准名称" style="min-width:14rem">
              <template #body="{ data }">
                {{ data.standard_name || '-' }}
              </template>
            </Column>
            <Column field="status" header="状态" style="width:8rem">
              <template #body="{ data }">
                <Tag :value="data.status" :severity="statusSeverity(data.status)" />
              </template>
            </Column>
            <Column field="saved_path" header="保存路径" style="min-width:14rem">
              <template #body="{ data }">
                <span class="text-sm">{{ data.saved_path || '-' }}</span>
              </template>
            </Column>
            <Column field="error" header="错误信息" style="min-width:10rem">
              <template #body="{ data }">
                <span class="text-sm text-red-500">{{ data.error || '-' }}</span>
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.download-import {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1rem;
}
.input-area {
  display: flex;
  flex-direction: column;
}
.file-upload {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.stats {
  display: flex;
  gap: 1rem;
}
.actions {
  display: flex;
  align-items: center;
}
.invalid-list {
  max-height: 200px;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .stats {
    flex-direction: column;
  }
}
</style>
