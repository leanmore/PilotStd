<script setup lang="ts">
/**
 * AppInput — 跨端设计系统（DS）统一文本输入（阶段二 · 模块一骨架）。
 *
 * 规则来源：docs/reference/ui-system.md §11.5 组件契约表
 *   - 四档形态由 `type` 分叉：text / password / number / textarea
 *   - 结构性类型（file / radio / hidden / checkbox 等）原样透传给原生 <input>，配合 `bare`
 *   - 三档尺寸：l / m / s，单行高度取 --input-height-*（语义独立于 --btn-height-*）
 *   - 圆角统一 --ds-radius-md；聚焦用 box-shadow: var(--focus-ring) 外发光
 *   - 禁用态取 --disabled-bg / --disabled-text（A-53 接线后的唯一口径）
 *   - 样式值全部来自 design-tokens.css 与主题变量，组件内不写字面量
 *
 * 门禁：业务代码禁止直接 import PrimeVue InputText/InputNumber/Password/Textarea、
 * 也禁止原生 <input>/<textarea>（custom/no-raw-input）。本组件是该规则的唯一收口点。
 *
 * ── 为什么按 type 分叉而不是让调用方自己选组件 ──
 * 门禁文案（no-raw-input.js）与规范（ui-system.md §11.5）都承诺
 * 「<AppInput type="textarea" :rows="n">」「<AppInput type="number">」是合法写法。
 * 若把 type 直接经 $attrs 落到原生 <input> 上，`type="textarea"` 会被浏览器**静默降级**
 * 成单行框（不报错、测试也能过），`type="number"` 则回传字符串且 min/step 无人消费。
 * 故这里显式分叉，把"错的写法"变成"对的渲染"。
 *
 * ── 结构性类型为什么不分叉 ──
 * file / radio / hidden / checkbox 这些没有"DS 视觉"，只是原生控件的不同形态；
 * 它们的可用性完全取决于原生属性（accept / value / checked / multiple）与浏览器行为，
 * 包一层 PrimeVue 反而会破坏 `display:none` 的上传域与 radio 的 `v-model` 分组语义。
 * 故这类 type **原样透传**给 InputText 内部的原生 <input>，配 `bare` 使用（§11.4 的官方逃生舱）。
 *
 * ── v-model 回传类型（按 type 分叉，与 ui-system.md §11.5 一致）──
 *   text / password / textarea → string（清空归一为 ''）
 *   number                     → number（清空回传 null）
 *   结构性类型                  → string（原生 input 的 DOM 值；radio 请用 :model-value + 闭包保住原类型）
 *
 * ── variant 为什么必须显式传 outlined（P0 缺陷 A）──
 * @primevue/core 的 BaseInput.$variant 是 `this.variant ?? this.$primevue.config.inputStyle || …`：
 * variant 为 null 时**无条件**读 `this.$primevue.config`。而本仓有一类「只测文案」的测试
 * （如 src/views/CommonI18n.test.ts 的 RegisterView / RouteDebugPanel 用例）故意不装
 * PrimeVue 插件，AppInput 一渲染就抛 `Cannot read properties of undefined (reading 'config')`。
 * 四个分叉显式传 variant="outlined" 后 $variant 短路、不再碰 $primevue；且 outlined 正是
 * 本组件的形态（--surface 底 + --border 描边），与 filled 无关。回归用例见 AppInput.test.ts。
 *
 * ── bare 逃生舱 ──
 * 走 PrimeVue 官方 unstyled 模式（四个底层组件都支持）：零基础视觉，外观由宿主 class 全权负责。
 * 不用 CSS 逐条清零，是为了避免把 0/transparent/auto 这类结构性字面量再写进组件
 * （G-055 的 ds-skeleton 基线只登记真正需要的）。
 */
import { computed } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Password from 'primevue/password'
import Textarea from 'primevue/textarea'

defineOptions({ name: 'AppInput', inheritAttrs: false })

type InputSize = 'l' | 'm' | 's'

/**
 * 形态枚举分三组：
 *  - DS 分叉组（text/password/number/textarea）：有自己的令牌视觉与 v-model 类型语义；
 *  - 原生 type 透传组（date/time/datetime-local/email/tel/url/search）：浏览器自带 UI，
 *    仍走 InputText 的 `:type` 原样透传，但**不加**结构性语义（可以有 DS 描边/尺寸）；
 *  - 结构性组（file/radio/hidden/checkbox）：无 DS 视觉，原样透传给原生 <input>，必须配 bare。
 * 显式枚举而非 `string & {}`：保住 number/password/textarea 在模板里的类型收窄。
 */
type InputType =
  | 'text'
  | 'password'
  | 'number'
  | 'textarea'
  | 'date'
  | 'time'
  | 'datetime-local'
  | 'email'
  | 'tel'
  | 'url'
  | 'search'
  | 'file'
  | 'radio'
  | 'hidden'
  | 'checkbox'

const props = withDefaults(
  defineProps<{
    /** 受控值（v-model）；类型随 type 分叉：number → number|null，其余 → string */
    modelValue?: string | number | null
    /** 形态：单行文本 / 密码 / 数字 / 多行文本 / 结构性（file/radio/hidden/checkbox） */
    type?: InputType
    /** 尺寸档：l / m / s（默认 m）
     *  ⚠️ 本 prop 有意遮蔽 PrimeVue 各原语的 size（small/large 两档）：
     *     DS 的三档与 PrimeVue 的两档不同构，且高度改由 --input-height-* 决定，
     *     透传下去反而会被 Aura 的 p-inputtext-sm/lg 内边距二次撑开。 */
    size?: InputSize
    /** 多行行数（仅 type="textarea" 生效；高度由 rows 撑开，见下方样式注释） */
    rows?: number
    /** 明文切换按钮（仅 type="password" 生效；为 true 时底层改用 PrimeVue Password） */
    toggleMask?: boolean
    /** 数字增减按钮（仅 type="number" 生效） */
    showButtons?: boolean
    /** 数字下限（仅 type="number" 生效） */
    min?: number
    /** 数字上限（仅 type="number" 生效） */
    max?: number
    /** 数字步进（仅 type="number" 生效） */
    step?: number
    /** 数字最小小数位（仅 type="number" 生效） */
    minFractionDigits?: number
    /** 数字最大小数位（仅 type="number" 生效；用于「25 显示成 25.00」这类固定精度） */
    maxFractionDigits?: number
    disabled?: boolean
    /** 校验失败态：描边改 --danger（同时透传 PrimeVue 的 invalid 语义） */
    invalid?: boolean
    /** 裸样式：不施加任何基础视觉，供结构性控件使用 */
    bare?: boolean
  }>(),
  {
    modelValue: '',
    type: 'text',
    size: 'm',
    rows: 3,
    toggleMask: false,
    showButtons: false,
    min: undefined,
    max: undefined,
    step: undefined,
    minFractionDigits: undefined,
    maxFractionDigits: undefined,
    disabled: false,
    invalid: false,
    bare: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:modelValue', value: number | null): void
}>()

/**
 * 四个分叉统一显式传 outlined（P0 缺陷 A，原因见文件头注释）：
 * 非 null 的 variant 让 @primevue/core 的 BaseInput.$variant 短路，不再读 $primevue.config，
 * 于是「故意不装 PrimeVue 插件、只测文案」的用例（CommonI18n.test.ts 等）不再抛 TypeError。
 * 常量而非内联字面量，是为了让四个分叉的取值只有一个改动点。
 */
const DS_INPUT_VARIANT = 'outlined' as const

/** 密码 + toggleMask 才切 PrimeVue Password；否则密码形态由 InputText 的 type 属性承担 */
const usePassword = computed(() => props.type === 'password' && props.toggleMask)

/** 根 class：bare 时只留标记 class，不带任何基础视觉 class。
 *
 * 关键设计：`app-input` 是「基础外观」class（自带背景/描边/圆角/内边距），
 * 只发给**本身就是视觉主体**的分叉（text / password 无明文切换 / textarea / 结构性类型 ——
 * 它们的根节点就是原生 input/textarea）。
 * number（根是 span 外壳）与 password+toggleMask（根是 div 外壳）的视觉在内层元素上，
 * 若给它们也加 `app-input`，就得再用 background:transparent / border:none / padding:0
 * 一条条抵消掉 —— 那会往组件里塞结构性字面量（G-055 会拦）。故这两类只拿修饰 class。
 *
 * textarea **不挂 `app-input--${size}`**（P0 缺陷 B）：尺寸类里有
 * `height: --input-height-*`（令牌引用），多行框吃到固定高度就会被压回一行，
 * 而 `min-height` 只能抬下限、压不过 height。多行框的高度由 rows + 上下内边距 +
 * line-height 撑开（--input-textarea-min-height 只兜住空内容时的下限），
 * 字号档对多行框也没有意义，故只保留 `.app-input--textarea`。
 */
const rootClass = computed(() => {
  if (props.bare) return ['app-input--bare']
  const size = `app-input--${props.size}`
  const invalid = props.invalid ? { 'app-input--invalid': true } : {}
  if (props.type === 'number') return ['app-input--number', size, invalid]
  if (usePassword.value) return ['app-input--password', size, invalid]
  if (props.type === 'textarea') return ['app-input', 'app-input--textarea', invalid]
  return ['app-input', `app-input--${props.type}`, size, invalid]
})

/**
 * 归一化写值：
 *   - number：PrimeVue 清空时回传 null，这里保持 null（不回退成 ''，否则下游 `typeof` 判断会错）
 *   - 其余：清空时回传 ''，避免 v-model 在 undefined / '' 之间抖动
 */
function onUpdate(value: string | number | null | undefined): void {
  if (props.type === 'number') {
    emit('update:modelValue', typeof value === 'number' ? value : null)
    return
  }
  emit('update:modelValue', typeof value === 'string' ? value : '')
}

/** 供模板里做类型断言用（避免在模板中写 any / as） */
function asString(value: string | number | null | undefined): string {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: string | number | null | undefined): number | null {
  return typeof value === 'number' ? value : null
}
</script>

<template>
  <Password
    v-if="usePassword"
    v-bind="$attrs"
    :model-value="asString(modelValue)"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :variant="DS_INPUT_VARIANT"
    :toggle-mask="toggleMask"
    :feedback="false"
    :class="rootClass"
    @update:model-value="onUpdate"
  />
  <InputNumber
    v-else-if="type === 'number'"
    v-bind="$attrs"
    :model-value="asNumber(modelValue)"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :variant="DS_INPUT_VARIANT"
    :show-buttons="showButtons"
    :min="min"
    :max="max"
    :step="step"
    :min-fraction-digits="minFractionDigits"
    :max-fraction-digits="maxFractionDigits"
    :class="rootClass"
    @update:model-value="onUpdate"
  />
  <Textarea
    v-else-if="type === 'textarea'"
    v-bind="$attrs"
    :model-value="asString(modelValue)"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :variant="DS_INPUT_VARIANT"
    :rows="rows"
    :class="rootClass"
    @update:model-value="onUpdate"
  />
  <InputText
    v-else
    v-bind="$attrs"
    :model-value="asString(modelValue)"
    :type="type"
    :disabled="disabled"
    :invalid="invalid"
    :unstyled="bare"
    :variant="DS_INPUT_VARIANT"
    :class="rootClass"
    @update:model-value="onUpdate"
  />
</template>

<style scoped>
/* ═══ 单行控件（text / password 无明文切换 / 结构性类型）═══
   基础外观：颜色 / 描边 / 圆角 / 字号全部取令牌 */
.app-input {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--ds-radius-md);
  font-size: var(--font-size-13);
  padding-inline: var(--space-12);
  transition: border-color var(--transition), box-shadow var(--transition), background-color var(--transition);
}

/* 尺寸档：高度取 --input-height-*。单行 input 的内容在内容盒内自动垂直居中，
   故 padding-block 保持 0，不靠上下内边距撑高（9px 上下 + 13px 字号会把 34px 撑爆）。
   ⚠️ 这组 height 只作用于单行分叉：textarea 的 rootClass 里**不挂** `app-input--${size}`
   （见 rootClass 注释），否则固定高度会把 rows 撑出的多行压回一行。 */
.app-input--l {
  height: var(--input-height-lg);
  font-size: var(--font-size-15);
  padding-inline: var(--space-16);
}
.app-input--m {
  height: var(--input-height-md);
}
.app-input--s {
  height: var(--input-height-sm);
  font-size: var(--font-size-12);
  padding-inline: var(--space-10);
}

/* 四态：hover / focus / invalid / disabled */
.app-input:enabled:hover {
  border-color: var(--text-dim);
}
.app-input:enabled:focus {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-input::placeholder {
  color: var(--text-dim);
}

/* 校验失败：描边恒为 --danger（压过 hover / focus 的描边色，聚焦外发光保留） */
.app-input--invalid,
.app-input--invalid:enabled:hover,
.app-input--invalid:enabled:focus {
  border-color: var(--danger);
}

.app-input:disabled {
  background: var(--disabled-bg);
  color: var(--disabled-text);
  border-color: var(--border);
  cursor: not-allowed;
}

/* ═══ 多行（textarea）：不套固定高度 ═══
   固定 height 会把多行截断成一行。高度由 rows 撑开（行数 × 行高 + 上下内边距），
   --input-textarea-min-height 只兜住"内容为空时塌成一条线"的下限；
   resize: vertical 允许用户自行拉高（横向拉伸会破坏页面栅格）。 */
.app-input--textarea {
  min-height: var(--input-textarea-min-height);
  padding: var(--space-9) var(--space-12);
  line-height: var(--line-height-body);
  resize: vertical;
}

/* ═══ 数字：InputNumber 的视觉落在内层 .p-inputnumber-input 上
   （根 span 是 inline-flex 外壳，本组件不给它基础外观 class，故无需抵消）═══ */
.app-input--number :deep(.p-inputnumber-input) {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  color: var(--text);
  padding-inline: var(--space-12);
  transition: border-color var(--transition), box-shadow var(--transition), background-color var(--transition);
}
.app-input--number :deep(.p-inputnumber-input:enabled:hover) {
  border-color: var(--text-dim);
}
.app-input--number :deep(.p-inputnumber-input:enabled:focus) {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-input--number :deep(.p-inputnumber-input::placeholder) {
  color: var(--text-dim);
}
/* 尺寸档要落在内层 input 上；根 span 不设高度，避免与内部 input 的高度打架 */
.app-input--number.app-input--l :deep(.p-inputnumber-input) {
  height: var(--input-height-lg);
  font-size: var(--font-size-15);
  padding-inline: var(--space-16);
}
.app-input--number.app-input--m :deep(.p-inputnumber-input) {
  height: var(--input-height-md);
}
.app-input--number.app-input--s :deep(.p-inputnumber-input) {
  height: var(--input-height-sm);
  font-size: var(--font-size-12);
  padding-inline: var(--space-10);
}
.app-input--number.app-input--invalid :deep(.p-inputnumber-input),
.app-input--number.app-input--invalid :deep(.p-inputnumber-input:enabled:hover),
.app-input--number.app-input--invalid :deep(.p-inputnumber-input:enabled:focus) {
  border-color: var(--danger);
}
/* 增减按钮：与输入框共用描边口径，hover 用抬升面 */
.app-input--number :deep(.p-inputnumber-button) {
  background: var(--surface);
  border-color: var(--border);
  color: var(--text-secondary);
}
.app-input--number :deep(.p-inputnumber-button:not(:disabled):hover) {
  background: var(--surface-raised);
  color: var(--text);
}
/* 禁用态：内层 input 与按钮都要换色（根 span 上没有 disabled 伪类可用） */
.app-input--number:has(:disabled) :deep(.p-inputnumber-input) {
  background: var(--disabled-bg);
  color: var(--disabled-text);
  border-color: var(--border);
}
.app-input--number:has(:disabled) :deep(.p-inputnumber-button) {
  background: var(--disabled-bg);
  color: var(--disabled-text);
  border-color: var(--border);
}

/* ═══ 密码（toggleMask）：Password 的视觉落在内层 .p-password-input 上
   （根 div 是 p-inputwrapper 外壳，本组件不给它基础外观 class，故无需抵消）═══ */
.app-input--password :deep(.p-password-input) {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--ds-radius-md);
  color: var(--text);
  padding-inline: var(--space-12);
  transition: border-color var(--transition), box-shadow var(--transition), background-color var(--transition);
}
.app-input--password :deep(.p-password-input:enabled:hover) {
  border-color: var(--text-dim);
}
.app-input--password :deep(.p-password-input:enabled:focus) {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
}
.app-input--password :deep(.p-password-input::placeholder) {
  color: var(--text-dim);
}
.app-input--password.app-input--l :deep(.p-password-input) {
  height: var(--input-height-lg);
  font-size: var(--font-size-15);
  padding-inline: var(--space-16);
}
.app-input--password.app-input--m :deep(.p-password-input) {
  height: var(--input-height-md);
}
.app-input--password.app-input--s :deep(.p-password-input) {
  height: var(--input-height-sm);
  font-size: var(--font-size-12);
  padding-inline: var(--space-10);
}
.app-input--password.app-input--invalid :deep(.p-password-input) {
  border-color: var(--danger);
}
/* 明文切换图标：继承文字层级，不单独设色 */
.app-input--password :deep(.p-password-toggle-mask-icon) {
  color: var(--text-secondary);
}
.app-input--password:has(:disabled) :deep(.p-password-input) {
  background: var(--disabled-bg);
  color: var(--disabled-text);
  border-color: var(--border);
}
.app-input--password:has(:disabled) :deep(.p-password-toggle-mask-icon) {
  color: var(--disabled-text);
}
</style>
