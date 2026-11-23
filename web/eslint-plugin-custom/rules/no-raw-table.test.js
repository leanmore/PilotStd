// no-raw-table 规则单测（2026-11-22 DS 阶段三 · 模块二）
import { RuleTester } from 'eslint'
import vueParser from 'vue-eslint-parser'

import rule from './no-raw-table.js'

const rt = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    parser: vueParser,
  },
})

rt.run('no-raw-table', rule, {
  valid: [
    // 业务代码用 AppTable + Column：合法
    {
      filename: 'src/views/Foo.vue',
      code:
        '<template><AppTable :value="rows" paginator :rows="20">' +
        '<Column field="id" header="ID" /></AppTable></template>',
    },
    // 业务代码用 AppDialog：合法
    {
      filename: 'src/views/Foo.vue',
      code:
        '<template><AppDialog v-model:visible="show" header="详情"><p>x</p></AppDialog></template>',
    },
    // 树形表格走 AppTable bare 逃生舱：仍合法（门禁只拦 PrimeVue 原语与原生 table）
    {
      filename: 'src/views/Foo.vue',
      code: '<template><AppTable bare :value="rows" /></template>',
    },
    // AppTable 封装点内部允许直接 import 并渲染 PrimeVue DataTable
    {
      filename: 'src/components/ui/AppTable.vue',
      code:
        "<script setup>import DataTable from 'primevue/datatable'</script>" +
        '<template><DataTable :value="rows" /></template>',
    },
    // AppDialog 封装点内部允许 PrimeVue Dialog + ConfirmDialog
    {
      filename: 'src/components/ui/AppDialog.vue',
      code:
        "<script setup>import Dialog from 'primevue/dialog'</script>" +
        '<template><Dialog v-model:visible="show" /></template>',
    },
    // 测试文件豁免（fixture/断言目标）
    {
      filename: 'src/views/Foo.test.ts',
      code: "import DataTable from 'primevue/datatable'",
    },
    // e2e 豁免
    {
      filename: 'src/e2e/table.spec.ts',
      code: "import Dialog from 'primevue/dialog'",
    },
    // PrimeVue 全局注册点豁免
    {
      filename: 'src/main.ts',
      code: "import ConfirmDialog from 'primevue/confirmdialog'",
    },
    // 表格里的普通单元格标签不拦（只拦 <table> 本身）
    {
      filename: 'src/views/Foo.vue',
      code: '<template><AppTable :value="rows"><Column field="a" /></AppTable></template>',
    },
  ],
  invalid: [
    // 原生 <table> 手写数据表
    {
      filename: 'src/views/Foo.vue',
      code:
        '<template><table class="data-table"><thead><tr><th>A</th></tr></thead>' +
        '<tbody><tr><td>1</td></tr></tbody></table></template>',
      errors: [{ messageId: 'rawTable' }],
    },
    // PrimeVue <DataTable>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><DataTable :value="rows" /></template>',
      errors: [{ messageId: 'primeDataTable' }],
    },
    // PrimeVue <TreeTable>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><TreeTable :value="nodes" /></template>',
      errors: [{ messageId: 'primeTreeTable' }],
    },
    // PrimeVue <DataGrid>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><DataGrid :value="items" /></template>',
      errors: [{ messageId: 'primeDataGrid' }],
    },
    // PrimeVue <Dialog>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><Dialog v-model:visible="show" header="x" /></template>',
      errors: [{ messageId: 'primeDialog' }],
    },
    // PrimeVue <ConfirmDialog>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><ConfirmDialog /></template>',
      errors: [{ messageId: 'primeConfirmDialog' }],
    },
    // PrimeVue <DynamicDialog>
    {
      filename: 'src/components/Foo.vue',
      code: '<template><DynamicDialog /></template>',
      errors: [{ messageId: 'primeDynamicDialog' }],
    },
    // Prime 前缀别名同样拦
    {
      filename: 'src/components/Foo.vue',
      code: '<template><PrimeDataTable :value="rows" /><PrimeDialog /></template>',
      errors: [{ messageId: 'primeDataTable' }, { messageId: 'primeDialog' }],
    },
    // 脚本里 import PrimeVue 表格/弹窗组件
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import DataTable from 'primevue/datatable'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Dialog from 'primevue/dialog'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: "<script setup>import ConfirmDialog from 'primevue/confirmdialog'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: "<script setup>import TreeTable from 'primevue/treetable'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    // 同一文件多命中：按控件逐条报
    {
      filename: 'src/views/Foo.vue',
      code: '<template><table><tr><td>1</td></tr></table><Dialog /><DataTable :value="rows" /></template>',
      errors: [
        { messageId: 'rawTable' },
        { messageId: 'primeDialog' },
        { messageId: 'primeDataTable' },
      ],
    },
  ],
})
