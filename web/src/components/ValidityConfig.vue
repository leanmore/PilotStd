<script setup lang="ts">
// ValidityConfig.vue — 时效性检查配置组件（从 ValidityConfigView 提取）
import { ref, onMounted, computed } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import { getValidityConfig, putValidityConfig, runValidityCheck, getValidityHistory, type ValidityConfig, type ValidityHistoryItem } from '@/api/validity'

const config = ref<ValidityConfig>({
  frequency: 'weekly', execute_time: '03:00', batch_size: 50,
  batch_interval: 5, check_ratio: 25, update_interval: 28,
})
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
  loading.value = true; errMsg.value = ''
  try { config.value = await getValidityConfig() }
  catch (e: any) { errMsg.value = e.response?.data?.error || '加载配置失败' }
  finally { loading.value = false }
}

async function doSave() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    await putValidityConfig(config.value)
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch (e: any) { errMsg.value = e.response?.data?.error || '保存失败' }
  finally { saving.value = false }
}

defineExpose({ doSave })

async function doRun() {
  running.value = true; runResult.value = ''
  try {
    const r = await runValidityCheck()
    runResult.value = `检查完成：${r.checked} 条，${r.changed} 条状态变更`
    loadHistory()
  } catch (e: any) { runResult.value = `失败: ${e.response?.data?.error || e.message}` }
  finally { running.value = false; setTimeout(() => runResult.value = '', 6000) }
}

// ── 执行记录（扩展版） ──
const history = ref<ValidityHistoryItem[]>([])
const histTotal = ref(0)
const histPage = ref(1)
const histPageSize = 20
const filterStatus = ref<string | null>(null)
const filterStart = ref('')
const filterEnd = ref('')
const detailItem = ref<ValidityHistoryItem | null>(null)
const detailVisible = ref(false)

const statusOptions = [
  { label: '全部', value: null },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

async function loadHistory() {
  try {
    const r = await getValidityHistory({ page: histPage.value, page_size: histPageSize })
    history.value = r.items
    histTotal.value = r.total
  } catch { /* 非关键 */ }
}

function onSearch() { histPage.value = 1; loadHistory() }
function onReset() { filterStatus.value = null; filterStart.value = ''; filterEnd.value = ''; histPage.value = 1; loadHistory() }
function showDetail(item: ValidityHistoryItem) { detailItem.value = item; detailVisible.value = true }

const totalPages = computed(() => Math.max(1, Math.ceil(histTotal.value / histPageSize)))
const pages = computed(() => {
  const tp = totalPages.value; const p = histPage.value
  const r: number[] = []
  let s = Math.max(1, p - 2); let e = Math.min(tp, p + 2)
  if (e - s < 4) { if (s === 1) e = Math.min(tp, s + 4); else s = Math.max(1, e - 4) }
  for (let i = s; i <= e; i++) r.push(i)
  return r
})

onMounted(() => { loadConfig(); loadHistory() })
</script>

<template>
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>
    <Message v-if="runResult" severity="info" :closable="false">{{ runResult }}</Message>

    <!-- 检查策略 -->
    <div class="section-title">检查策略</div>
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
    <div class="actions-row">
      <Button icon="pi pi-play" label="立即执行一次" severity="secondary" :loading="running" @click="doRun" />
      <Button icon="pi pi-save" label="保存配置" :loading="saving" @click="doSave" />
    </div>

    <!-- 执行记录 -->
    <div class="section-title" style="margin-top:24px">执行记录</div>
    <div class="filter-row">
      <div class="filter-item">
        <label>状态</label>
        <Select v-model="filterStatus" :options="statusOptions" optionLabel="label" optionValue="value" />
      </div>
      <div class="filter-item">
        <label>开始日期</label>
        <InputText v-model="filterStart" type="date" size="small" />
      </div>
      <div class="filter-item">
        <label>结束日期</label>
        <InputText v-model="filterEnd" type="date" size="small" />
      </div>
      <div class="filter-actions">
        <Button label="筛选" icon="pi pi-search" size="small" severity="success" @click="onSearch" />
        <Button label="重置" icon="pi pi-refresh" size="small" severity="secondary" @click="onReset" />
      </div>
    </div>

    <div class="table-meta">
      <span>共 {{ histTotal }} 条记录</span>
      <span v-if="histTotal > 0">第 {{ histPage }}/{{ totalPages }} 页</span>
    </div>

    <table v-if="history.length" class="data-table">
      <thead>
        <tr><th>执行时间</th><th>检查条数</th><th>状态变更</th><th>结果</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="h in history" :key="h.check_date">
          <td>{{ h.check_date }}</td>
          <td>{{ h.checked_count }}</td>
          <td>{{ h.changed_count }}条</td>
          <td><Tag :severity="h.status === 'success' ? 'success' : 'danger'" :value="h.status === 'success' ? '完成' : '失败'" /></td>
          <td><Button label="详情" size="small" severity="secondary" text @click="showDetail(h)" /></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">暂无执行记录</p>

    <div v-if="totalPages > 1" class="pagination">
      <Button icon="pi pi-angle-left" size="small" severity="secondary" text :disabled="histPage <= 1" @click="histPage--; loadHistory()" />
      <Button v-for="p in pages" :key="p" :label="String(p)" size="small" :severity="p === histPage ? 'primary' : 'secondary'" text @click="histPage = p; loadHistory()" />
      <Button icon="pi pi-angle-right" size="small" severity="secondary" text :disabled="histPage >= totalPages" @click="histPage++; loadHistory()" />
    </div>

    <Dialog v-model:visible="detailVisible" header="执行详情" :style="{width:'400px'}" modal>
      <div v-if="detailItem" class="detail">
        <div class="detail-row"><span>执行日期</span><span>{{ detailItem.check_date }}</span></div>
        <div class="detail-row"><span>检查条数</span><span>{{ detailItem.checked_count }}</span></div>
        <div class="detail-row"><span>状态变更</span><span>{{ detailItem.changed_count }}条</span></div>
        <div class="detail-row"><span>结果</span><Tag severity="success" value="完成" /></div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.section-title { font-weight: 600; color: var(--text-heading); font-size: 14px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; margin-bottom: 14px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; font-weight: 500; color: var(--text-dim); }
.actions-row { display: flex; gap: 10px; margin-bottom: 8px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; margin-bottom: 12px; }
.filter-item { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
.filter-item label { font-size: 11px; font-weight: 500; color: var(--text-dim); }
.filter-actions { display: flex; gap: 8px; align-items: flex-end; }
.table-meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-dim); margin-bottom: 8px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { padding: 7px 8px; text-align: left; border-bottom: 1px solid var(--border); }
.data-table th { font-weight: 600; color: var(--text-dim); font-size: 11px; text-transform: uppercase; }
.empty { color: var(--text-dim); font-size: 13px; padding: 16px 0; text-align: center; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 2px; margin-top: 10px; }
.detail { display: flex; flex-direction: column; gap: 10px; font-size: 13px; }
.detail-row { display: flex; justify-content: space-between; align-items: center; }
.detail-row span:first-child { color: var(--text-dim); }
</style>
