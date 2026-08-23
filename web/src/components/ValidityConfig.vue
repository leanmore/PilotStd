<script setup lang="ts">
defineOptions({ name: 'ValidityConfig' })
// ValidityConfig.vue — 时效性检查配置组件（从 ValidityConfigView 提取）
import { ref, onMounted, computed, watch } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DatePicker from 'primevue/datepicker'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import { getValidityConfig, putValidityConfig, runValidityCheck, getValidityHistory, type ValidityConfig, type ValidityHistoryItem } from '@/api/validity'
import { getItem, setItem } from '@/lib/storage'

// 兼容旧后端：可能返回 update_interval（天）代替 total_weeks
interface LegacyValidityResponse extends Partial<ValidityConfig> {
  update_interval?: number
}

/** 提取 axios 错误消息 */
function getErrorMessage(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { error?: string; details?: string[] } }; message?: string }
  return err.response?.data?.error
    || (err.response?.data?.details?.join('; '))
    || err.message
    || fallback
}

const config = ref<ValidityConfig>({
  first_weekday: 1, execute_time: '03:00',
  total_weeks: 4, frequency_weeks: 1,
  batch_size: 50, batch_interval: 5, check_ratio: 25,
})

// ====== 周几选项：number (1-7) → 中文标签 ======
const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日'] as const

const weekdayOptions = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 7 },
]

// ====== 时间桥接：DatePicker(Date) ↔ 后端 string('HH:mm') ======
function parseTimeToDate(v: string | undefined): Date {
  const [h, m] = (v || '03:00').split(':').map(Number)
  const d = new Date()
  d.setHours(Number.isFinite(h) ? h : 3, Number.isFinite(m) ? m : 0, 0, 0)
  return d
}

function formatDateToTime(d: Date | null): string {
  if (!d) return '03:00'
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

const executeTimeDate = computed<Date | null>({
  get: () => parseTimeToDate(config.value.execute_time),
  set: (d: Date | null) => {
    config.value.execute_time = formatDateToTime(d)
  },
})

const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const saved = ref(false)
const runResult = ref('')
const errMsg = ref('')

// ✅ #43: 计算执行次数
const executionCount = computed(() => {
  const { total_weeks, frequency_weeks } = config.value
  if (!total_weeks || !frequency_weeks || frequency_weeks < 1) return 0
  return total_weeks / frequency_weeks
})

// ✅ #43: 计算每次覆盖比例（F / T × 100，联动后 F 可能 ≠ 1，不能再用 100/T 假设）
const checkRatioDisplay = computed(() => {
  const total = config.value.total_weeks
  const freq = config.value.frequency_weeks
  if (!total || total < 4 || !freq || freq < 1) return 0
  return ((freq / total) * 100).toFixed(1)
})

// 首次执行时间（展示用）
const firstExecutionTime = computed(() => {
  const idx = Math.max(0, Math.min((config.value.first_weekday ?? 1) - 1, 6))
  return `周${WEEKDAY_LABELS[idx]} ${config.value.execute_time}`
})

// ✅ #43: 校验是否可保存
const isValid = computed(() => {
  const { total_weeks, frequency_weeks } = config.value
  if (!total_weeks || total_weeks < 4) return false
  if (!frequency_weeks || frequency_weeks < 1) return false
  if (frequency_weeks > total_weeks) return false
  if (executionCount.value < 4) return false
  return true
})

// 防循环标志：代码赋值触发组件 @update:modelValue 链路时防止双向联动死循环
let isUpdating = false

/**
 * 正向联动：T 或 F 变化 → 重算 P
 * 边界保护：F 截断到 [1, T]；T 由组件 blur 时 clamp 到 [4, 52]
 * Null 防御（方案 A）：PrimeVue allowEmpty=true，清空输入后 modelValue 为 null，
 * 入口直接跳过，避免 NaN 污染。不用 allow-empty=false 是因为其清空回退值为 0，
 * 0 进入 F/T 会产生 Infinity，比 null 更危险；且组件 blur clamp 已保证合法范围。
 */
function onTotalOrFreqChange() {
  if (isUpdating) return
  isUpdating = true
  try {
    const T = config.value.total_weeks
    let F = config.value.frequency_weeks
    if (T == null || F == null || !Number.isFinite(T) || !Number.isFinite(F)) return

    // 边界保护：F 不能大于 T，不能小于 1
    if (F > T) F = T
    if (F < 1) F = 1
    config.value.frequency_weeks = F

    // 重算 P（Math.round(x*10000)/100 规避 IEEE 754 浮点精度边缘风险）
    const newRatio = Math.round((F / T) * 10000) / 100
    if (config.value.check_ratio !== newRatio) {
      config.value.check_ratio = newRatio
    }
  } finally {
    isUpdating = false
  }
}

/**
 * 反向联动：P 变化 → 反推 F（标准四舍五入，.5 向上取整）→ 用最终 F 回写 P
 */
function onCheckRatioChange() {
  if (isUpdating) return
  isUpdating = true
  try {
    const T = config.value.total_weeks
    const P = config.value.check_ratio
    if (T == null || P == null || !Number.isFinite(T) || !Number.isFinite(P)) return

    // 反推 F（标准四舍五入，.5 向上取整）
    let newF = Math.round((P / 100) * T)

    // 边界保护：F 必须在 [1, T] 区间内
    if (newF < 1) newF = 1
    if (newF > T) newF = T

    config.value.frequency_weeks = newF

    // 用最终的 F 回写 P（保证 F 为整数时 P 严格对应）
    const finalRatio = Math.round((newF / T) * 10000) / 100
    if (config.value.check_ratio !== finalRatio) {
      config.value.check_ratio = finalRatio
    }
  } finally {
    isUpdating = false
  }
}

async function loadConfig() {
  loading.value = true; errMsg.value = ''
  try {
    const raw = await getValidityConfig('/settings')
    config.value = { ...config.value, ...raw }
    // 兼容旧后端：可能只返回 update_interval（天），无 total_weeks
    const legacy = raw as LegacyValidityResponse
    if (!config.value.total_weeks && legacy.update_interval) {
      config.value.total_weeks = Math.max(4, Math.round(legacy.update_interval / 7))
    }
  }
  catch (e: unknown) { errMsg.value = getErrorMessage(e, '加载配置失败') }
  finally { loading.value = false }
}

async function doSave() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    await putValidityConfig(config.value)
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch (e: unknown) {
    errMsg.value = getErrorMessage(e, '保存失败')
  }
  finally { saving.value = false }
}

defineExpose({ doSave })

async function doRun() {
  running.value = true; runResult.value = ''
  try {
    const r = await runValidityCheck()
    runResult.value = `检查完成：${r.checked} 条，${r.changed} 条状态变更`
    loadHistory()
  } catch (e: unknown) { runResult.value = `失败: ${getErrorMessage(e, '未知错误')}` }
  finally { running.value = false; setTimeout(() => runResult.value = '', 6000) }
}

// ── 执行记录（扩展版） ──
const history = ref<ValidityHistoryItem[]>([])
const histTotal = ref(0)
const histPage = ref(Number(getItem('validity_hist_page')) || 1)
const histPageSize = 20
const filterStatus = ref<string | null>(null)
const filterStart = ref('')
const filterEnd = ref('')

function loadValidityFilters() {
  try {
    const raw = getItem('validity_filters')
    if (!raw) return
    const f = JSON.parse(raw)
    filterStatus.value = f.st ?? null
    filterStart.value = f.sd ?? ''
    filterEnd.value = f.ed ?? ''
  } catch { /* ignore */ }
}

function saveValidityFilters() {
  setItem('validity_filters', JSON.stringify({
    st: filterStatus.value, sd: filterStart.value, ed: filterEnd.value,
  }))
}

watch([filterStatus, filterStart, filterEnd], saveValidityFilters, { deep: true })
watch(histPage, (v) => setItem('validity_hist_page', String(v)))
const detailItem = ref<ValidityHistoryItem | null>(null)
const detailVisible = ref(false)

const statusOptions = [
  { label: '全部', value: null },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

async function loadHistory() {
  try {
    const r = await getValidityHistory({ page: histPage.value, page_size: histPageSize }, '/settings')
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

onMounted(() => { loadValidityFilters(); loadConfig(); loadHistory() })
</script>

<template>
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>
    <Message v-if="runResult" severity="info" :closable="false">{{ runResult }}</Message>

    <!-- 检查策略 -->
    <div class="section-title">检查策略</div>
    <div class="form-grid">
      <!-- 首次执行周几 -->
      <div class="field">
        <label>首次执行（周几）</label>
        <Select v-model="config.first_weekday" :options="weekdayOptions" optionLabel="label" optionValue="value" class="field-control" />
      </div>
      <!-- 首次执行时间 -->
      <div class="field">
        <label>首次执行（时间）</label>
        <DatePicker v-model="executeTimeDate" timeOnly hourFormat="24" class="field-control" />
      </div>
      <!-- ✅ #43: 总周期（联动源：T 变化 → 重算 P） -->
      <div class="field">
        <label>总周期（周）</label>
        <InputNumber
          v-model="config.total_weeks"
          :min="4"
          :max="52"
          :step="1"
          show-buttons
          @update:modelValue="onTotalOrFreqChange"
        />
        <small class="field-hint">完成全部检查所需总周数（4~52 周）</small>
      </div>
      <!-- ✅ #43: 执行频率（联动源：F 变化 → 重算 P） -->
      <div class="field">
        <label>执行频率（周）</label>
        <InputNumber
          v-model="config.frequency_weeks"
          :min="1"
          :max="config.total_weeks"
          :step="1"
          show-buttons
          @update:modelValue="onTotalOrFreqChange"
        />
        <small class="field-hint">每隔几周执行一次</small>
      </div>
      <div class="field">
        <label>单批大小（条/批）</label>
        <InputNumber v-model="config.batch_size" :min="1" show-buttons />
      </div>
      <div class="field">
        <label>批间隔（秒）</label>
        <InputNumber v-model="config.batch_interval" :min="1" show-buttons />
      </div>
      <!-- ✅ #43: 检查比例（联动源：P 变化 → 反推 F 并回写 P） -->
      <div class="field">
        <label>检查比例（%）</label>
        <InputNumber
          v-model="config.check_ratio"
          :min="0.01"
          :max="100"
          :step="0.1"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          show-buttons
          @update:modelValue="onCheckRatioChange"
        />
        <small class="field-hint">修改后自动回填对应执行频率</small>
      </div>
    </div>

    <!-- ✅ #43: 自动计算结果 -->
    <div class="computed-info">
      <div class="info-item">
        <span class="info-label">执行次数：</span>
        <span class="info-value" :class="{ 'info-error': executionCount < 4 }">
          {{ executionCount.toFixed(1) }} 次
          <span v-if="executionCount < 4" class="error-msg">（需 >= 4 次）</span>
        </span>
      </div>
      <div class="info-item">
        <span class="info-label">每次覆盖：</span>
        <span class="info-value">约 {{ checkRatioDisplay }}%</span>
      </div>
      <div class="info-item">
        <span class="info-label">首次执行时间：</span>
        <span class="info-value">{{ firstExecutionTime }}</span>
      </div>
    </div>

    <div class="actions-row">
      <Button
        label="保存配置"
        icon="pi pi-save"
        :loading="saving"
        :disabled="!isValid"
        @click="doSave"
      />
      <Button icon="pi pi-play" label="立即执行一次" severity="secondary" :loading="running" @click="doRun" />
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
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px 20px; margin-bottom: 14px; align-items: start; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 12px; font-weight: 500; color: var(--text-dim); }
.field-control { width: 100%; height: 36px; }
.form-grid :deep(.p-inputnumber) { height: 36px; }
.field-hint { font-size: 11px; color: var(--text-dim); margin-top: 2px; }

/* ✅ #43: 自动计算结果区 */
.computed-info {
  display: flex; gap: 24px; padding: 12px 16px;
  background: var(--surface-raised); border-radius: var(--radius-sm);
  margin-bottom: 14px; flex-wrap: wrap;
}
.info-item { display: flex; align-items: center; gap: 4px; font-size: 13px; }
.info-label { color: var(--text-dim); }
.info-value { font-weight: 600; color: var(--text-bright); }
.info-error { color: var(--danger); }
.error-msg { font-size: 12px; font-weight: 400; }

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
.time-group { display: flex; align-items: center; gap: 0.25rem; }
.time-input { width: 4.5rem; }
.separator { font-weight: bold; padding: 0 0.25rem; }
</style>
