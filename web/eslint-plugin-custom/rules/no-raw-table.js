// custom/no-raw-table.js
// DS 门禁：业务代码的数据表格与弹窗必须使用 <AppTable> / <AppDialog>，
// 禁止手写原生 <table>，禁止直接使用 PrimeVue 表格/弹窗组件。
//
// 阶段三（2026-11-22）：以 warn 落地并统计存量；分批替换完成后升 error。
// 豁免：App* 封装自身（src/components/ui/App*.vue）、PrimeVue 全局注册点（src/main.ts）、
//       测试文件、e2e。
//
// 实现要点（实测，与 no-raw-button.js / no-raw-input.js 完全一致）：
// ESLint 10 + vue-eslint-parser 下直接写 `VElement` 访问器不会触发；
// 必须经 eslint-plugin-vue 的 `defineTemplateBodyVisitor` 才能遍历模板。
// 该包只提供 `dist/index.js`（无 `lib/utils` 子路径）；其 utils 是 CommonJS，
// ESM 命名导入拿不到函数（实测 undefined），故用默认导入再解构。

import vueUtils from 'eslint-plugin-vue/dist/utils/index.js'

// CJS 双层 default：函数挂在 vueUtils.default 上（实测 Object.keys 只有 'default'）
const { defineTemplateBodyVisitor } = vueUtils.default

// 原生标签 → messageId（业务代码里手写的数据表；AppTable 内部不用 <table>，由 PrimeVue 渲染，不冲突）
const RAW_TAGS = {
  table: 'rawTable',
}

// PrimeVue 表格组件名 → messageId（含 Prime 前缀别名）
const PRIME_TABLE_TAGS = {
  DataTable: 'primeDataTable',
  TreeTable: 'primeTreeTable',
  DataGrid: 'primeDataGrid',
  PrimeDataTable: 'primeDataTable',
  PrimeTreeTable: 'primeTreeTable',
  PrimeDataGrid: 'primeDataGrid',
}

// PrimeVue 弹窗组件名 → messageId（含 Prime 前缀别名）
const PRIME_DIALOG_TAGS = {
  Dialog: 'primeDialog',
  ConfirmDialog: 'primeConfirmDialog',
  DynamicDialog: 'primeDynamicDialog',
  PrimeDialog: 'primeDialog',
  PrimeConfirmDialog: 'primeConfirmDialog',
  PrimeDynamicDialog: 'primeDynamicDialog',
}

// 脚本侧禁止直接 import 的 PrimeVue 入口
const PRIME_MODULES = new Set([
  'primevue/datatable',
  'primevue/treetable',
  'primevue/datagrid',
  'primevue/dialog',
  'primevue/confirmdialog',
  'primevue/dynamicdialog',
])

// DS 封装点：AppTable/AppDialog 内部允许用 PrimeVue 原语（样式与行为在封装内收口）
const ALLOWED_FILES = ['src/main.ts']

function isAllowed(filename) {
  const norm = filename.replace(/\\/g, '/')
  // src/components/ui/App*.vue —— AppTable/AppDialog/... 的封装点
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
        '业务代码禁止手写原生 <table> 数据表，禁止直接使用 PrimeVue 表格（DataTable/TreeTable/DataGrid）' +
        '与弹窗（Dialog/ConfirmDialog/DynamicDialog）组件，必须使用 <AppTable>/<AppDialog>' +
        '（见 docs/reference/ui-system.md 十二）。',
    },
    schema: [],
    messages: {
      rawTable:
        '禁止在业务代码手写原生 <table> 数据表：请改用 <AppTable :value="rows"> + <Column field="..." :header="..." />；' +
        '高度定制的表格（树形/合并单元格）用 <AppTable bare>（docs/reference/ui-system.md 十二）。',
      primeDataTable:
        '禁止直接使用 PrimeVue <DataTable>：请改用 <AppTable>（表头/斑马纹/行 hover/分页器由 DS 统一，' +
        '见 docs/reference/ui-system.md 十二）。',
      primeTreeTable:
        '禁止直接使用 PrimeVue <TreeTable>：请改用 <AppTable bare>（树形表格需零样式透传，' +
        '见 docs/reference/ui-system.md 十二）。',
      primeDataGrid:
        '禁止直接使用 PrimeVue <DataGrid>：请改用 <AppTable>；确需 DataGrid 语义时走 <AppTable bare> 并在此登记豁免' +
        '（docs/reference/ui-system.md 十二）。',
      primeDialog:
        '禁止直接使用 PrimeVue <Dialog>：请改用 <AppDialog v-model:visible="..." :header="...">' +
        '（圆角/内边距/关闭按钮由 DS 统一，见 docs/reference/ui-system.md 十二）。',
      primeConfirmDialog:
        '禁止直接使用 PrimeVue <ConfirmDialog>：请改用 <AppDialog> 或 DS 统一确认流程' +
        '（docs/reference/ui-system.md 十二）。',
      primeDynamicDialog:
        '禁止直接使用 PrimeVue <DynamicDialog>：请改用 <AppDialog>（docs/reference/ui-system.md 十二）。',
      primeImport:
        '禁止直接 import PrimeVue 表格/弹窗组件（{{source}}）：请改用 App* 封装' +
        '（AppTable/AppDialog，见 docs/reference/ui-system.md 十二）。',
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
          const tableMessageId = PRIME_TABLE_TAGS[raw]
          if (tableMessageId) {
            context.report({ node, messageId: tableMessageId })
            return
          }
          const dialogMessageId = PRIME_DIALOG_TAGS[raw]
          if (dialogMessageId) {
            context.report({ node, messageId: dialogMessageId })
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
