// custom/no-raw-input.js
// DS 门禁：业务代码必须使用 <AppInput> / <AppSelect> / <AppCheckbox> / <AppToggle> /
// <AppDatePicker>，禁止原生 <input>/<select>/<textarea> 与 PrimeVue 输入组件。
//
// 阶段三（2026-11-22）：以 warn 落地并统计存量；分批替换完成后升 error。
// 豁免：App* 封装自身（src/components/ui/App*.vue）、PrimeVue 全局注册点（src/main.ts）、
//       测试文件、e2e。
//
// 实现要点（实测，与 no-raw-button.js 完全一致）：
// ESLint 10 + vue-eslint-parser 下直接写 `VElement` 访问器不会触发；
// 必须经 eslint-plugin-vue 的 `defineTemplateBodyVisitor` 才能遍历模板。
// 该包只提供 `dist/index.js`（无 `lib/utils` 子路径）；其 utils 是 CommonJS，
// ESM 命名导入拿不到函数（实测 undefined），故用默认导入再解构。

import vueUtils from 'eslint-plugin-vue/dist/utils/index.js'

// CJS 双层 default：函数挂在 vueUtils.default 上（实测 Object.keys 只有 'default'）
const { defineTemplateBodyVisitor } = vueUtils.default

// 原生标签 → messageId
const RAW_TAGS = {
  input: 'rawInput',
  select: 'rawSelect',
  textarea: 'rawTextarea',
}

// PrimeVue 组件名 → messageId（含常见别名 PrimeInputText 等）
const PRIME_TAGS = {
  InputText: 'primeInputText',
  InputNumber: 'primeInputNumber',
  Textarea: 'primeTextarea',
  Password: 'primePassword',
  Select: 'primeSelect',
  Dropdown: 'primeSelect',
  Checkbox: 'primeCheckbox',
  ToggleSwitch: 'primeToggleSwitch',
  DatePicker: 'primeDatePicker',
  SelectButton: 'primeSelectButton',
  PrimeInputText: 'primeInputText',
  PrimeInputNumber: 'primeInputNumber',
  PrimeTextarea: 'primeTextarea',
  PrimePassword: 'primePassword',
  PrimeSelect: 'primeSelect',
  PrimeCheckbox: 'primeCheckbox',
  PrimeToggleSwitch: 'primeToggleSwitch',
  PrimeDatePicker: 'primeDatePicker',
  PrimeSelectButton: 'primeSelectButton',
}

// 脚本侧禁止直接 import 的 PrimeVue 入口
const PRIME_MODULES = new Set([
  'primevue/inputtext',
  'primevue/select',
  'primevue/checkbox',
  'primevue/toggleswitch',
  'primevue/datepicker',
  'primevue/inputnumber',
  'primevue/password',
  'primevue/textarea',
  'primevue/selectbutton',
  'primevue/dropdown',
])

// DS 封装点：App* 组件内部允许用原生标签 / PrimeVue 原语（样式与行为在封装内收口）
const ALLOWED_FILES = ['src/main.ts']

function isAllowed(filename) {
  const norm = filename.replace(/\\/g, '/')
  // src/components/ui/App*.vue —— AppButton/AppInput/AppSelect/... 的封装点
  if (/(^|\/)components\/ui\/App[^/]*\.vue$/.test(norm)) return true
  if (ALLOWED_FILES.some((f) => norm.endsWith(f))) return true
  if (/\.(test|spec)\.(ts|js|vue)$/.test(norm)) return true
  if (norm.includes('/e2e/')) return true
  return false
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        '业务代码禁止直接使用原生 <input>/<select>/<textarea> 或 PrimeVue 输入组件，' +
        '必须使用 <AppInput>/<AppSelect>/<AppCheckbox>/<AppToggle>/<AppDatePicker>' +
        '（见 docs/reference/ui-system.md）。',
    },
    schema: [],
    messages: {
      rawInput:
        '禁止原生 <input>：请改用 <AppInput v-model="..." size="l|m|s">；' +
        '结构性用法（type="file"/"radio" 等）用 <AppInput bare>（docs/reference/ui-system.md 十一）。',
      rawSelect:
        '禁止原生 <select>：请改用 <AppSelect v-model="..." :options="..." optionLabel="..." optionValue="..." />' +
        '（docs/reference/ui-system.md 十一）。',
      rawTextarea:
        '禁止原生 <textarea>：请改用 <AppInput type="textarea" :rows="n" v-model="..." />' +
        '（docs/reference/ui-system.md 十一）。',
      primeInputText:
        '禁止直接使用 PrimeVue <InputText>：请改用 <AppInput>（尺寸/四态由 DS 统一，见 docs/reference/ui-system.md 十一）。',
      primeInputNumber:
        '禁止直接使用 PrimeVue <InputNumber>：请改用 <AppInput type="number">（docs/reference/ui-system.md 十一）。',
      primeTextarea:
        '禁止直接使用 PrimeVue <Textarea>：请改用 <AppInput type="textarea" :rows="n">（docs/reference/ui-system.md 十一）。',
      primePassword:
        '禁止直接使用 PrimeVue <Password>：请改用 <AppInput type="password">（docs/reference/ui-system.md 十一）。',
      primeSelect:
        '禁止直接使用 PrimeVue <Select>/<Dropdown>：请改用 <AppSelect>（docs/reference/ui-system.md 十一）。',
      primeCheckbox:
        '禁止直接使用 PrimeVue <Checkbox>：请改用 <AppCheckbox>（docs/reference/ui-system.md 十一）。',
      primeToggleSwitch:
        '禁止直接使用 PrimeVue <ToggleSwitch>：请改用 <AppToggle>（docs/reference/ui-system.md 十一）。',
      primeDatePicker:
        '禁止直接使用 PrimeVue <DatePicker>：请改用 <AppDatePicker>（docs/reference/ui-system.md 十一）。',
      primeSelectButton:
        '禁止直接使用 PrimeVue <SelectButton>：请改用 <AppSelect>（分段单选形态）；' +
        '若确需原语，走 App* 封装并在此登记豁免（docs/reference/ui-system.md 十一）。',
      primeImport:
        '禁止直接 import PrimeVue 输入组件（{{source}}）：请改用 App* 封装' +
        '（AppInput/AppSelect/AppCheckbox/AppToggle/AppDatePicker，见 docs/reference/ui-system.md 十一）。',
    },
  },
  create(context) {
    const filename = context.filename || context.getFilename() || ''
    if (isAllowed(filename)) return {}

    return defineTemplateBodyVisitor(
      context,
      {
        VElement(node) {
          const raw = node.rawName || node.name || ''
          const rawMessageId = RAW_TAGS[raw]
          if (rawMessageId) {
            context.report({ node, messageId: rawMessageId })
            return
          }
          const primeMessageId = PRIME_TAGS[raw]
          if (primeMessageId) {
            context.report({ node, messageId: primeMessageId })
          }
        },
      },
      {
        ImportDeclaration(node) {
          const src = node.source?.value
          if (typeof src === 'string' && PRIME_MODULES.has(src)) {
            context.report({ node, messageId: 'primeImport', data: { source: src } })
          }
        },
      },
    )
  },
}
