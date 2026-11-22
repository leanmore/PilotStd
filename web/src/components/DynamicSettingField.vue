<script setup lang="ts">
/**
 * DynamicSettingField.vue — Schema 驱动的动态设置字段渲染器。
 *
 * 用法：
 *   <DynamicSettingField field-key="network.proxy" />
 *
 * 组件从注入的 settingsSchema 中按 key 查找字段元数据，
 * 从注入的 settingsConfig 中读写值，自动处理嵌套路径。
 *
 * ── 控件口径（阶段三 · 模块一）──
 * 输入控件统一走 DS 封装（AppInput / AppSelect），本文件不再出现原生
 * <input>/<select>（门禁 custom/no-raw-input，见 docs/reference/ui-system.md 十一）。
 * 视觉（尺寸/圆角/四态）由 App* 承担，本文件只保留**布局**（宽度 100%）。
 *
 * ⚠️ 本文件是 schema 驱动的写入收口点，emitVal / emitNumber / emitTags / emitBool
 *    的**写入语义必须与替换前逐字一致**（setNested 的数组保留逻辑不能变）。
 *    区别只在"值从哪来"：原生控件从 DOM 事件里读 e.target.value，
 *    App* 组件从 `update:modelValue` 直接拿值 —— 不再读 DOM。
 */
import { computed, inject, unref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppInput from '@/components/ui/AppInput.vue'
import AppSelect from '@/components/ui/AppSelect.vue'

defineOptions({ name: 'DynamicSettingField' })

const { t } = useI18n()

const i18nKey = computed(() => `settings.${resolved.value.key}`)
const label = computed(() => {
  const translated = t(i18nKey.value)
  return translated !== i18nKey.value
    ? translated
    : (resolved.value.key.split('.').pop() || '').replace(/_/g, ' ')
})

/** 设置字段的合法值类型 */
type SettingValue = string | number | boolean | (string | number)[]

export interface SchemaField {
  key: string
  tab: string
  field_type: string
  default: unknown
  placeholder?: string
  options?: { label: string; value: string | number }[]
  help_text?: string
  required?: boolean
}

const props = defineProps<{
  fieldKey: string
}>()

// 从父组件注入
const schemaMapRaw = inject<Record<string, SchemaField>>('settingsSchema', {})
const schemaMap = computed<Record<string, SchemaField>>(() => unref(schemaMapRaw))
const cfg = inject<Record<string, unknown>>('settingsConfig', {})

/** 从注入的 schemaMap 中查找字段定义 */
const resolved = computed<SchemaField>(() => {
  const found = schemaMap.value[props.fieldKey]
  if (found) return found
  return { key: props.fieldKey, tab: '', field_type: 'input', default: '' }
})

/** 按路径读取嵌套值 */
function getNested(path: string): unknown {
  const parts = path.split('.')
  let v: unknown = unref(cfg)
  for (const p of parts) {
    if (v == null || typeof v !== 'object') return undefined
    v = (v as Record<string, unknown>)[p]
  }
  return v
}

/** 按路径写入嵌套值（就地修改，保留响应式） */
function setNested(path: string, val: SettingValue) {
  const root = unref(cfg) as Record<string, unknown>
  const parts = path.split('.')
  let o: Record<string, unknown> = root
  for (let i = 0; i < parts.length - 1; i++) {
    if (!o[parts[i]] || typeof o[parts[i]] !== 'object') o[parts[i]] = {}
    o = o[parts[i]] as Record<string, unknown>
  }
  o[parts[parts.length - 1]] = val
}

// ── 事件处理 ──

function emitVal(val: SettingValue) {
  setNested(props.fieldKey, val)
}

/** 数字写入：若原值是数组则保留第二元素 */
function emitNumber(val: number) {
  const cur = getNested(props.fieldKey)
  if (Array.isArray(cur) && cur.length >= 2) {
    setNested(props.fieldKey, [val, cur[1] as number])
  } else {
    setNested(props.fieldKey, val)
  }
}

/**
 * 布尔写入：AppSelect 的 update:modelValue 直接给回选中的 optionValue（'false' / 'true'），
 * 直接与 'true' 比较即可。
 * （替换前是原生 <select>，靠 @change 读 (e.target as HTMLSelectElement).value；
 *   AppSelect 是 div 复合结构，没有 target.value，读 DOM 既拿不到值也不稳定。）
 */
function emitBool(val: unknown) {
  setNested(props.fieldKey, val === 'true')
}

/** 标签写入：AppInput 回传的字符串按逗号切分（原逻辑不变，只是值来源从 DOM 事件改为 v-model） */
function emitTags(raw: string | number | null) {
  const tags = String(raw ?? '').split(',').map((s: string) => s.trim()).filter(Boolean)
  setNested(props.fieldKey, tags)
}

/** 文本类控件写值：AppInput 的 v-model 是 string（清空归一为 ''），与原生 input.value 同语义 */
function onTextInput(val: string | number | null) {
  emitVal(String(val ?? ''))
}

/**
 * 数字控件写值：AppInput type="number" 回传 number | null（清空为 null）。
 * 旧实现是 parseFloat(input.value) || 0 —— 空串 / 非法输入都归 0，这里保持同一口径。
 */
function onNumberInput(val: string | number | null) {
  const n = typeof val === 'number' && Number.isFinite(val) ? val : 0
  emitNumber(n)
}

/** 下拉选择写值：optionValue 原样回传（schema 里的 options.value 已是 string | number） */
function onSelectInput(val: unknown) {
  emitVal(val as SettingValue)
}

/** 开关选项：保持「否 / 是」两项、值仍是字符串 'false' / 'true'（与原 <option value> 一致） */
const boolOptions = computed(() => [
  { label: t('common.no'), value: 'false' },
  { label: t('common.yes'), value: 'true' },
])

/** 下拉选项：schema 的 options 已是 { label, value }，映射后显式声明契约 */
const selectOptions = computed(() =>
  (resolved.value.options || []).map(opt => ({ label: opt.label, value: opt.value })),
)

// ── 展示值 ──

/** 文本类展示值：非字符串统一按原生 input 的 value 语义转字符串 */
function textVal(): string {
  const raw = getNested(props.fieldKey) ?? resolved.value.default
  if (raw == null) return ''
  return typeof raw === 'string' ? raw : String(raw)
}

/** 回退分支展示值（旧实现不套 default） */
function fallbackVal(): string {
  const raw = getNested(props.fieldKey)
  if (raw == null) return ''
  return typeof raw === 'string' ? raw : String(raw)
}

/** 开关展示值：'false' / 'true' 字符串，与 boolOptions 的 value 对应 */
function boolStr(): string {
  return String(getNested(props.fieldKey) ?? resolved.value.default)
}

/** 下拉展示值：原样给 AppSelect（optionValue 比对靠值相等） */
function selectVal(): unknown {
  return getNested(props.fieldKey) ?? resolved.value.default
}

function tagsStr(arr: unknown): string {
  return Array.isArray(arr) ? arr.join(', ') : ''
}

/** 标签展示值（保持原表达式：getNested ?? default 再 tagsStr） */
function tagsVal(): string {
  return tagsStr(getNested(props.fieldKey) ?? resolved.value.default)
}

/** 数字读取：若存储值是数组则取 [0] */
function numberVal(): number {
  const v = getNested(props.fieldKey)
  if (Array.isArray(v)) return (v[0] as number) ?? 0
  return (v as number) ?? 0
}
</script>

<template>
  <div class="setting-field">
    <label class="field-label">
      {{ label }}
      <span v-if="resolved.required" class="required">*</span>
    </label>

    <!-- 文本框 -->
    <AppInput
      v-if="resolved.field_type === 'input'"
      class="field-control"
      :model-value="textVal()"
      :placeholder="resolved.placeholder || ''"
      @update:model-value="onTextInput"
    />

    <!-- 密码框 -->
    <AppInput
      v-else-if="resolved.field_type === 'password'"
      class="field-control"
      type="password"
      autocomplete="off"
      :model-value="textVal()"
      :placeholder="resolved.placeholder || ''"
      @update:model-value="onTextInput"
    />

    <!-- 数字（自动处理数组值：取 [0] 展示，写入时保留 [1]） -->
    <AppInput
      v-else-if="resolved.field_type === 'number'"
      class="field-control"
      type="number"
      :step="0.1"
      :model-value="numberVal()"
      @update:model-value="onNumberInput"
    />

    <!-- 开关（保持原「下拉两项」交互形态，值仍为 'false' / 'true'） -->
    <AppSelect
      v-else-if="resolved.field_type === 'toggle'"
      class="field-control"
      :model-value="boolStr()"
      :options="boolOptions"
      option-label="label"
      option-value="value"
      @update:model-value="emitBool"
    />

    <!-- 下拉选择 -->
    <AppSelect
      v-else-if="resolved.field_type === 'select'"
      class="field-control"
      :model-value="selectVal()"
      :options="selectOptions"
      option-label="label"
      option-value="value"
      @update:model-value="onSelectInput"
    />

    <!-- 标签输入（逗号分隔） -->
    <AppInput
      v-else-if="resolved.field_type === 'tags'"
      class="field-control"
      :model-value="tagsVal()"
      :placeholder="resolved.placeholder || ''"
      @update:model-value="emitTags"
    />

    <!-- cron 表达式 -->
    <AppInput
      v-else-if="resolved.field_type === 'cron'"
      class="field-control"
      :model-value="textVal()"
      :placeholder="resolved.placeholder || '0 3 * * *'"
      @update:model-value="onTextInput"
    />

    <!-- 回退 -->
    <AppInput
      v-else
      class="field-control"
      :model-value="fallbackVal()"
      @update:model-value="onTextInput"
    />

    <span v-if="resolved.help_text" class="help-text">{{ resolved.help_text }}</span>
  </div>
</template>

<style scoped>
.setting-field {
  display: contents;
}
.field-label {
  font-size: var(--font-size-14);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  white-space: nowrap;
}
.required {
  color: var(--danger);
}
.help-text {
  font-size: var(--font-size-11);
  color: var(--text-dim);
  grid-column: 2;
}
/* 只保留布局：尺寸 / 圆角 / 四态由 AppInput / AppSelect 承担（§11.4 禁止业务页写输入框样式） */
.field-control {
  width: 100%;
}
</style>
