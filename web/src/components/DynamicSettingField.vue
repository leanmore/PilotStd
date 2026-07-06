<script setup lang="ts">
/**
 * DynamicSettingField.vue — Schema 驱动的动态设置字段渲染器。
 *
 * 用法：
 *   <DynamicSettingField field-key="network.proxy" />
 *
 * 组件从注入的 settingsSchema 中按 key 查找字段元数据，
 * 从注入的 settingsConfig 中读写值，自动处理嵌套路径。
 */
import { computed, inject, unref } from 'vue'

defineOptions({ name: 'DynamicSettingField' })

export interface SchemaField {
  key: string
  tab: string
  field_type: string
  default: any
  placeholder?: string
  options?: { label: string; value: any }[]
  help_text?: string
  required?: boolean
}

const props = defineProps<{
  fieldKey: string
}>()

// 从父组件注入
const schemaMap = inject<Record<string, any>>('settingsSchema', {})
const cfg = inject<Record<string, any>>('settingsConfig', {})

/** 从注入的 schemaMap 中查找字段定义 */
const resolved = computed<SchemaField>(() => {
  const found = schemaMap[props.fieldKey]
  if (found) return found as SchemaField
  return { key: props.fieldKey, tab: '', field_type: 'input', default: '' }
})

/** 按路径读取嵌套值（兼容 ref / reactive） */
function getNested(path: string): any {
  const parts = path.split('.')
  let v: any = unref(cfg)
  for (const p of parts) {
    if (v == null) return undefined
    v = v[p]
  }
  return v
}

/** 按路径写入嵌套值（就地修改，保留响应式） */
function setNested(path: string, val: any) {
  const root = unref(cfg)
  const parts = path.split('.')
  let o: any = root
  for (let i = 0; i < parts.length - 1; i++) {
    if (!o[parts[i]] || typeof o[parts[i]] !== 'object') o[parts[i]] = {}
    o = o[parts[i]]
  }
  o[parts[parts.length - 1]] = val
}

// ── 事件处理 ──

function emitVal(val: any) {
  setNested(props.fieldKey, val)
}

/** 数字写入：若原值是数组则保留第二元素（如 query_interval [min, max]） */
function emitNumber(val: number) {
  const cur = getNested(props.fieldKey)
  if (Array.isArray(cur) && cur.length >= 2) {
    setNested(props.fieldKey, [val, cur[1]])
  } else {
    setNested(props.fieldKey, val)
  }
}

function emitBool(e: Event) {
  setNested(props.fieldKey, (e.target as HTMLSelectElement).value === 'true')
}

function emitTags(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  const tags = raw.split(',').map((s: string) => s.trim()).filter(Boolean)
  setNested(props.fieldKey, tags)
}

function tagsStr(arr: any): string {
  return Array.isArray(arr) ? arr.join(', ') : ''
}

/** 数字读取：若存储值是数组则取 [0]，否则直接返回 */
function numberVal(): number {
  const v = getNested(props.fieldKey)
  if (Array.isArray(v)) return v[0] ?? resolved.value.default?.[0] ?? 0
  return v ?? resolved.value.default ?? 0
}
</script>

<template>
  <div class="setting-field">
    <label class="field-label">
      {{ resolved.key.split('.').pop()?.replace(/_/g, ' ') }}
      <span v-if="resolved.required" class="required">*</span>
    </label>

    <!-- 文本框 -->
    <input
      v-if="resolved.field_type === 'input'"
      :value="getNested(fieldKey) ?? resolved.default"
      @input="emitVal(($event.target as HTMLInputElement).value)"
      class="fi"
      :placeholder="resolved.placeholder || ''"
    />

    <!-- 密码框 -->
    <input
      v-else-if="resolved.field_type === 'password'"
      :value="getNested(fieldKey) ?? resolved.default"
      @input="emitVal(($event.target as HTMLInputElement).value)"
      class="fi"
      type="password"
      autocomplete="off"
      :placeholder="resolved.placeholder || ''"
    />

    <!-- 数字（自动处理数组值：取 [0] 展示，写入时保留 [1]） -->
    <input
      v-else-if="resolved.field_type === 'number'"
      :value="numberVal()"
      @input="emitNumber(parseFloat(($event.target as HTMLInputElement).value) || 0)"
      class="fi"
      type="number"
      step="0.1"
    />

    <!-- 开关 -->
    <select
      v-else-if="resolved.field_type === 'toggle'"
      :value="String(getNested(fieldKey) ?? resolved.default)"
      @change="emitBool"
      class="fi"
    >
      <option value="false">否</option>
      <option value="true">是</option>
    </select>

    <!-- 下拉选择 -->
    <select
      v-else-if="resolved.field_type === 'select'"
      :value="getNested(fieldKey) ?? resolved.default"
      @change="emitVal(($event.target as HTMLSelectElement).value)"
      class="fi"
    >
      <option
        v-for="opt in (resolved.options || [])"
        :key="opt.value"
        :value="opt.value"
      >{{ opt.label }}</option>
    </select>

    <!-- 标签输入（逗号分隔） -->
    <input
      v-else-if="resolved.field_type === 'tags'"
      :value="tagsStr(getNested(fieldKey) ?? resolved.default)"
      @input="emitTags"
      class="fi"
      :placeholder="resolved.placeholder || ''"
    />

    <!-- cron 表达式 -->
    <input
      v-else-if="resolved.field_type === 'cron'"
      :value="getNested(fieldKey) ?? resolved.default"
      @input="emitVal(($event.target as HTMLInputElement).value)"
      class="fi"
      :placeholder="resolved.placeholder || '0 3 * * *'"
    />

    <!-- 回退 -->
    <input
      v-else
      :value="getNested(fieldKey)"
      @input="emitVal(($event.target as HTMLInputElement).value)"
      class="fi"
    />

    <span v-if="resolved.help_text" class="help-text">{{ resolved.help_text }}</span>
  </div>
</template>

<style scoped>
.setting-field {
  display: contents;
}
.field-label {
  font-size: 13px;
  color: var(--text);
  text-transform: capitalize;
  white-space: nowrap;
}
.required {
  color: var(--danger);
}
.help-text {
  font-size: 11px;
  color: var(--text-dim);
  grid-column: 2;
}
.fi {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}
</style>
