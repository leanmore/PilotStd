<script setup lang="ts">
defineOptions({ name: 'TaskView' })
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { postScan, postQuery, postDownload, postNormalize, postArchive, getSettings } from '@/api'
import { getPipelineRun } from '@/api/tasks'
import type { PipelineRun } from '@/types/task'
import { getItem, setItem, removeItem } from '@/lib/storage'
import { restoreResultsFromStepResults, resolveActiveRun } from '@/utils/taskRestore'
import { useUserPreferences } from '@/composables/useUserPreferences'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import DataView from 'primevue/dataview'
import Paginator from 'primevue/paginator'
import { parseStandardNumber } from '@/utils/standardParser'
import LogBar from '@/components/LogBar.vue'

const { t } = useI18n()
const paths = ref<string[]>(['/inbox', '/standards'])
const { taskPath: selectedPath } = useUserPreferences()
const running = ref(false)
const currentStep = ref(-1)

// 步骤名存 key、渲染期翻译；旧版 localStorage 记录只有 label（中文），模板做回退
interface StepState { labelKey: string; label?: string; icon: string; status: 'wait'|'running'|'done'|'fail'; summary: string }
const steps = ref<StepState[]>([
  { labelKey: 'task.step.scan', icon: 'pi pi-search', status: 'wait', summary: '' },
  { labelKey: 'task.step.query', icon: 'pi pi-globe', status: 'wait', summary: '' },
  { labelKey: 'task.step.download', icon: 'pi pi-download', status: 'wait', summary: '' },
  { labelKey: 'task.step.normalize', icon: 'pi pi-pencil', status: 'wait', summary: '' },
  { labelKey: 'task.step.archive', icon: 'pi pi-folder-open', status: 'wait', summary: '' },
])

const scanResult = ref<any>(null)
const queryResult = ref<any>(null)
const downloadResult = ref<any>(null)
const normalizeResult = ref<any>(null)
const archiveResult = ref<any>(null)
const error = ref('')
const progress = ref(0)

// 管道运行追踪
const runId = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null
let pollFailCount = 0
const STEP_ORDER = ['scan', 'query', 'download', 'normalize', 'archive'] as const

/** 将后端 PipelineRun 状态映射到本地 steps */
function updateStepsFromRun(run: PipelineRun) {
  const currentIdx = STEP_ORDER.indexOf(run.current_step as typeof STEP_ORDER[number])
  for (let i = 0; i < STEP_ORDER.length; i++) {
    const s = steps.value[i]
    if (i < currentIdx && s.status !== 'done' && s.status !== 'fail') {
      s.status = 'done'
    } else if (i === currentIdx) {
      if (run.status === 'failed') {
        s.status = 'fail'
        s.summary = run.error_message || t('task.run_failed')
      } else if (run.status === 'completed') {
        s.status = 'done'
      } else {
        s.status = 'running'
      }
    }
  }
  progress.value = run.progress
  if (run.status === 'failed' && !error.value) {
    error.value = run.error_message || t('task.pipeline_failed')
  }
}

function startPolling() {
  if (!runId.value) return
  pollFailCount = 0
  pollTimer = setInterval(async () => {
    try {
      const run = await getPipelineRun(runId.value!)
      pollFailCount = 0
      updateStepsFromRun(run)
      if (run.status === 'completed' || run.status === 'failed') {
        stopPolling()
        // 终态清除持久化的 runId，避免重进时误恢复旧任务
        removeItem('task_active_run')
      }
    } catch {
      pollFailCount++
      if (pollFailCount >= 3) {
        stopPolling()
        if (!error.value) error.value = t('task.sync_failed')
      }
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onBeforeUnmount(() => { stopPolling() })

// ── 进度恢复：页面重进时从后端重建进行中的任务状态 ──
async function restoreActiveRun() {
  const resolved = await resolveActiveRun()
  if (!resolved) return
  runId.value = resolved.runId
  running.value = true
  updateStepsFromRun(resolved.run)
  const restored = restoreResultsFromStepResults(resolved.run.step_results)
  scanResult.value = restored.scan
  queryResult.value = restored.query
  downloadResult.value = restored.download
  normalizeResult.value = restored.normalize
  archiveResult.value = restored.archive
  startPolling()
}

// 任务历史 —— localStorage 持久化
interface TaskRecord {
  id: string; time: string; path: string
  scanCount: number; queryFound: number; dlSuccess: number; normCount: number
  status: 'success' | 'partial' | 'fail'
  steps: StepState[]
}
const history = ref<TaskRecord[]>([])
const selectedRecord = ref<TaskRecord | null>(null)

onMounted(() => {
  try {
    history.value = JSON.parse(localStorage.getItem('pilotstd_tasks') || '[]')
  } catch { history.value = [] }
  loadPaths()
  restoreActiveRun()
})

const historyPage = ref(Number(getItem('task_history_page')) || 0)
const historyRows = ref(10)

const paginatedHistory = computed(() => {
  const start = historyPage.value * historyRows.value
  return history.value.slice(start, start + historyRows.value)
})

function onHistoryPage(e: any) {
  historyPage.value = e.page
  setItem('task_history_page', String(e.page))
}

function saveHistory(status: 'success'|'partial'|'fail') {
  const record: TaskRecord = {
    id: Date.now().toString(36),
    time: new Date().toLocaleString('zh-CN'),
    path: selectedPath.value,
    scanCount: scanResult.value?.total || 0,
    queryFound: queryResult.value?.stats?.found || 0,
    dlSuccess: downloadResult.value?.stats?.success || 0,
    normCount: normalizeResult.value?.results?.length || 0,
    status,
    steps: JSON.parse(JSON.stringify(steps.value)),
  }
  history.value.unshift(record)
  if (history.value.length > 50) history.value = history.value.slice(0, 50)
  localStorage.setItem('pilotstd_tasks', JSON.stringify(history.value))
}

function viewRecord(r: TaskRecord) { selectedRecord.value = r }
function rerun(r: TaskRecord) { selectedPath.value = r.path; selectedRecord.value = null; runPipeline() }

function deleteRecord(r: TaskRecord) {
  if (!confirm(t('task.delete_confirm'))) return
  history.value = history.value.filter(item => item.id !== r.id)
  localStorage.setItem('pilotstd_tasks', JSON.stringify(history.value))
  if (selectedRecord.value?.id === r.id) selectedRecord.value = null
}

async function loadPaths() {
  try { const r = await getSettings(); paths.value = r.storage?.scan_paths || paths.value } catch {}
}

function setStep(i: number, status: 'wait'|'running'|'done'|'fail', summary = '') {
  steps.value[i].status = status
  steps.value[i].summary = summary
  progress.value = status === 'done' ? ((i + 1) / 5 * 100) : progress.value
}

async function runPipeline() {
  running.value = true; error.value = ''
  scanResult.value = queryResult.value = downloadResult.value = normalizeResult.value = archiveResult.value = null
  steps.value.forEach(s => { s.status = 'wait'; s.summary = '' })
  progress.value = 0
  runId.value = null
  stopPolling()
  let finalStatus: 'success'|'partial'|'fail' = 'success'

  try {
    // 步骤 0：扫描（发起方，run_id 由后端生成）
    currentStep.value = 0; setStep(0, 'running')
    const scan = await postScan(selectedPath.value)
    scanResult.value = scan
    runId.value = scan.run_id
    // 持久化 runId，供退出重进后恢复进度
    setItem('task_active_run', runId.value)
    // 启动后端状态轮询
    startPolling()
    setStep(0, 'done', t('task.scan_summary', { n: scan.total || 0, pdf: scan.pdf_count || 0, word: scan.word_count || 0 }))
    if (!scan.files?.length) { error.value = t('task.scan_no_files'); finalStatus = 'fail'; return }

    // 步骤 1：查询
    currentStep.value = 1; setStep(1, 'running')
    const numbers = (scan.files || []).map((f: any) => f.standard_number).filter(Boolean)
    if (numbers.length === 0) {
      setStep(1, 'done', t('task.scan_no_numbers')); error.value = t('task.scan_parse_failed'); finalStatus = 'partial'; return
    }
    const query = await postQuery(numbers, false, runId.value!)
    queryResult.value = query
    setStep(1, 'done', t('task.query_summary', { n: query.stats?.found || 0, m: query.stats?.downloadable || 0 }))

    // 步骤 2：下载
    currentStep.value = 2; setStep(2, 'running')
    const dlNums = (query.results || []).filter((r: any) => !r.is_adopted && r.match_status === 'exact').map((r: any) => r.standard_number).slice(0, 10)
    if (dlNums.length > 0) {
      const dl = await postDownload(dlNums, runId.value!)
      downloadResult.value = dl
      setStep(2, 'done', t('task.download_summary', { s: dl.stats?.success || 0, k: dl.stats?.skipped || 0 }))
    } else { setStep(2, 'done', t('task.download_empty')) }

    // 步骤 3：规范化
    currentStep.value = 3; setStep(3, 'running')
    const normItems = (scan.files || [])
      .filter((f: any) => f.standard_number)
      .map((f: any) => {
        // 优先透传 scan 返回的结构化字段，仅在缺失时回退到正则解析
        const parsed = (f.logical_code && f.number && f.year)
          ? { logical_code: f.logical_code, number: f.number, year: f.year }
          : parseStandardNumber(f.standard_number)

        if (!parsed) {
          console.warn('[Normalize] 跳过无法解析的标准号:', f.standard_number, '| 文件:', f.full_path) // i18n-allow: 开发者日志：跳过无法解析的标准号
          return null
        }

        return {
          source_path: f.full_path,
          new_filename: f.standard_number || f.logical_code || f.name,
          logical_code: parsed.logical_code,
          number: parsed.number,
          year: parsed.year,
        }
      })
      .filter((item): item is NonNullable<typeof item> => item != null)
    const norm = await postNormalize(normItems, runId.value!)
    normalizeResult.value = norm
    setStep(3, 'done', t('task.count_files', { n: norm.results?.length || 0 }))

    // 步骤 4：归档
    currentStep.value = 4; setStep(4, 'running')
    const archiveMap = new Map((norm.results || []).map((r: any) => [r.source_path, r.new_filename]))
    const archiveItems = (scan.files || []).filter((f: any) => archiveMap.has(f.full_path)).map((f: any) => ({
      source_path: f.full_path, new_filename: archiveMap.get(f.full_path) || f.name || '',
      logical_code: f.logical_code || '', number: f.number || 0, year: f.year || 0, std_name: f.std_name || f.name || '',
      num_prefix: f.num_prefix || '', ext: (f.name || '').toLowerCase().endsWith('.pdf') ? 'pdf' : 'doc',
    }))
    if (archiveItems.length > 0) {
      await postArchive(archiveItems, undefined, runId.value!)
      setStep(4, 'done', t('task.archive_done'))
    } else { setStep(4, 'done', t('task.archive_empty')) }

    progress.value = 100
  } catch (e: any) {
    setStep(currentStep.value, 'fail', e.response?.data?.error || e.message || t('task.unknown_error'))
    error.value = e.response?.data?.error || e.message || t('task.unknown_error')
    finalStatus = 'fail'
  } finally {
    running.value = false
    saveHistory(finalStatus)
    // 延迟停止轮询：给后端最后一次状态更新留时间
    setTimeout(() => { if (pollTimer) stopPolling() }, 5000)
  }
}

function stepSeverity(s: string) {
  if (s === 'done') return 'success'; if (s === 'running') return 'info'
  if (s === 'fail') return 'danger'; return 'secondary'
}
function statusSeverity(s: string) {
  if (s === 'success') return 'success'; if (s === 'partial') return 'warn'; return 'danger'
}
function statusLabel(s: string) {
  if (s === 'success') return t('task.status.done'); if (s === 'partial') return t('task.status.partial'); return t('task.status.failed')
}
</script>

<template>
  <div class="page-header">
    <div>
      <h1>{{ t('task.title') }}</h1>
      <p class="hint">{{ t('task.hint') }}</p>
    </div>
  </div>

  <!-- 路径选择 + 启动 -->
  <div class="card mb-3">
    <div class="controls">
      <select v-model="selectedPath" class="fi">
        <option v-for="p in paths" :key="p" :value="p">{{ p }}</option>
      </select>
      <Button :label="t('task.start')" icon="pi pi-play" :loading="running" @click="runPipeline" />
    </div>
  </div>

  <!-- 进度条 -->
  <ProgressBar v-if="running || progress > 0" :value="progress" class="mb-3" />

  <p v-if="error" class="err-msg mb-2">{{ error }}</p>

  <!-- 流水线步骤 -->
  <div class="pipeline">
    <div v-for="(step, i) in steps" :key="i" class="step" :class="step.status">
      <div class="step-indicator">
        <i v-if="step.status === 'done'" class="pi pi-check" />
        <i v-else-if="step.status === 'running'" class="pi pi-spin pi-spinner" />
        <i v-else-if="step.status === 'fail'" class="pi pi-times" />
        <span v-else class="step-num">{{ i + 1 }}</span>
      </div>
      <div class="step-info">
        <div class="step-label">{{ step.labelKey ? t(step.labelKey) : step.label }}</div>
        <div v-if="step.summary" class="step-summary">{{ step.summary }}</div>
      </div>
      <Tag :value="step.status === 'done' ? t('task.status.done') : step.status === 'running' ? t('task.status.running') : step.status === 'fail' ? t('task.status.failed') : t('task.status.pending')" :severity="stepSeverity(step.status)" />
    </div>
  </div>

  <!-- 扫描结果 -->
  <div v-if="scanResult" class="card mt-3">
    <div class="card-header">{{ t('task.scan_result') }}</div>
    <div class="stats-row">
      <Tag severity="success" :value="'PDF: ' + (scanResult.pdf_count || 0)" />
      <Tag severity="info" :value="'Word: ' + (scanResult.word_count || 0)" />
      <Tag severity="warn" :value="t('task.dup_skipped', { n: scanResult.dup_skipped || 0 })" />
      <Tag :value="t('task.total_files', { n: scanResult.total || 0 })" />
    </div>
  </div>

  <!-- 查询/下载/归档汇总 -->
  <div v-if="queryResult" class="card mt-3">
    <div class="card-header">{{ t('task.summary_title') }}</div>
    <div class="summary-grid">
      <div class="sum-item"><span class="sum-label">{{ t('task.step.query') }}</span><span class="sum-val">{{ t('task.count_items', { n: queryResult.stats?.found || 0 }) }}</span></div>
      <div class="sum-item"><span class="sum-label">{{ t('task.downloadable') }}</span><span class="sum-val">{{ t('task.count_items', { n: queryResult.stats?.downloadable || 0 }) }}</span></div>
      <div class="sum-item"><span class="sum-label">{{ t('task.download_success') }}</span><span class="sum-val">{{ t('task.count_items', { n: downloadResult?.stats?.success || 0 }) }}</span></div>
      <div class="sum-item"><span class="sum-label">{{ t('task.step.normalize') }}</span><span class="sum-val">{{ t('task.count_files', { n: normalizeResult?.results?.length || 0 }) }}</span></div>
    </div>
  </div>

  <!-- 任务历史 -->
  <div v-if="history.length" class="card mt-3">
    <div class="card-header">{{ t('task.history_title') }}</div>
    <DataView :value="paginatedHistory" size="small">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.id" class="p-2 border-bottom">
          <div class="flex" style="display:flex;gap:12px;align-items:center;padding:6px 0;border-bottom:1px solid var(--border-light)">
            <div style="flex:1;min-width:0">
              <div class="flex" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
                <span class="text-mono" style="font-size:13px;font-family:var(--mono)">{{ item.time }}</span>
                <span class="text-dim" style="font-size:12px;color:var(--text-dim)">{{ item.path }}</span>
              </div>
              <div class="flex" style="display:flex;gap:12px;font-size:12px;color:var(--text-dim);margin-top:4px">
                <span>{{ t('task.history_scan', { n: item.scanCount }) }}</span>
                <span>{{ t('task.history_query', { n: item.queryFound }) }}</span>
                <span>{{ t('task.history_download', { n: item.dlSuccess }) }}</span>
              </div>
            </div>
            <div class="flex" style="display:flex;gap:6px;align-items:center">
              <Tag :value="statusLabel(item.status)" :severity="statusSeverity(item.status)" />
              <Button :label="t('task.detail')" size="small" text @click="viewRecord(item)" />
              <Button :label="t('task.rerun')" size="small" text severity="info" @click="rerun(item)" />
              <Button :label="t('task.delete')" size="small" text severity="danger" @click="deleteRecord(item)" />
            </div>
          </div>
        </div>
      </template>
    </DataView>
    <Paginator :rows="historyRows" :totalRecords="history.length" @page="onHistoryPage" class="mt-2" />
  </div>

  <!-- 历史详情弹窗 -->
  <div v-if="selectedRecord" class="card mt-3">
    <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
      <span>{{ t('task.detail_title', { time: selectedRecord.time }) }}</span>
      <Button icon="pi pi-times" size="small" text @click="selectedRecord = null" />
    </div>
    <div class="pipeline">
      <div v-for="(step, i) in selectedRecord.steps" :key="i" class="step" :class="step.status">
        <div class="step-indicator">
          <i v-if="step.status === 'done'" class="pi pi-check" />
          <i v-else-if="step.status === 'fail'" class="pi pi-times" />
          <span v-else class="step-num">{{ i + 1 }}</span>
        </div>
        <div class="step-info">
          <div class="step-label">{{ step.labelKey ? t(step.labelKey) : step.label }}</div>
          <div v-if="step.summary" class="step-summary">{{ step.summary }}</div>
        </div>
        <Tag :value="step.status === 'done' ? t('task.status.done') : step.status === 'fail' ? t('task.status.failed') : t('task.status.pending')" :severity="stepSeverity(step.status)" />
      </div>
    </div>
  </div>

  <LogBar />
</template>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.controls { display: flex; gap: 12px; align-items: center; }
.fi { padding: 9px 13px; background: var(--bg); border: 1px solid var(--border); color: var(--text);
  border-radius: var(--radius-sm); font-size: 13px; min-width: 220px; outline: none; }
.fi:focus { border-color: var(--primary); box-shadow: var(--focus-ring); }
.err-msg { color: var(--danger); font-size: 12px; }
.mb-2 { margin-bottom: 12px; }
.mb-3 { margin-bottom: 16px; }
.mt-3 { margin-top: 16px; }

/* 流水线步骤 */
.pipeline {
  display: flex; flex-direction: column; gap: 0;
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}
.step {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px;
  background: var(--surface);
  border-bottom: 1px solid var(--border-light);
  transition: background 0.15s ease;
}
.step:last-child { border-bottom: none; }
.step.running { background: var(--primary-bg); }
.step.fail { background: rgba(239,68,68,0.06); }

.step-indicator {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--border);
  color: var(--text);
  font-size: 13px; font-weight: 600;
  flex-shrink: 0;
}
.step.done .step-indicator { background: var(--success, #10b981); color: #fff; }
.step.running .step-indicator { background: var(--primary); color: #fff; }
.step.fail .step-indicator { background: var(--danger, #ef4444); color: #fff; }

.step-info { flex: 1; min-width: 0; }
.step-label { font-size: 14px; font-weight: 500; color: var(--text-heading); }
.step-summary { font-size: 12px; color: var(--text-dim); margin-top: 2px; }

.stats-row { display: flex; gap: 8px; flex-wrap: wrap; }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.sum-item { display: flex; flex-direction: column; gap: 4px; padding: 10px; background: var(--bg); border-radius: var(--radius-sm); }
.sum-label { font-size: 12px; color: var(--text-dim); }
.sum-val { font-size: 18px; font-weight: 600; color: var(--text-heading); font-family: var(--mono); }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
.text-dim { color: var(--text-dim, #6b7280); }
.text-mono { font-family: var(--mono, 'Consolas', 'Courier New', monospace); }
.mt-2 { margin-top: 12px; }
</style>
