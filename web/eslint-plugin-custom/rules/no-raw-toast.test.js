// no-raw-toast 规则单测（2026-11-23 DS 阶段三 · 模块四）
import { RuleTester } from 'eslint'
import vueParser from 'vue-eslint-parser'

import rule from './no-raw-toast.js'

const rt = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    parser: vueParser,
  },
})

rt.run('no-raw-toast', rule, {
  valid: [
    // AppToast 封装自身允许用 PrimeVue Toast（封装点）
    {
      filename: 'src/components/ui/AppToast.vue',
      code: "<script setup>import Toast from 'primevue/toast'</script><template><Toast /></template>",
    },
    // useAppToast.ts 是服务封装点
    {
      filename: 'src/composables/useAppToast.ts',
      code: "import { useToast } from 'primevue/usetoast'",
    },
    // App.vue 是宿主挂载 + 全局绑定处
    {
      filename: 'src/App.vue',
      code: "<script setup>import { useToast } from 'primevue/usetoast'</script>",
    },
    // main.ts 是 PrimeVue 全局注册点
    {
      filename: 'src/main.ts',
      code: "import Toast from 'primevue/toast'",
    },
    // 业务代码用 useAppToast：合法
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import { useAppToast } from '@/composables/useAppToast'</script>",
    },
    // 测试文件豁免
    {
      filename: 'src/views/Foo.test.ts',
      code: "import { useToast } from 'primevue/usetoast'",
    },
    // e2e 豁免
    {
      filename: 'web/e2e/foo.spec.ts',
      code: "import Toast from 'primevue/toast'",
    },
  ],
  invalid: [
    // 业务代码直接用 <Toast />
    {
      filename: 'src/views/Foo.vue',
      code: '<template><Toast /></template>',
      errors: [{ messageId: 'rawToastHost' }],
    },
    // Prime 前缀别名
    {
      filename: 'src/views/Foo.vue',
      code: '<template><PrimeToast /></template>',
      errors: [{ messageId: 'rawToastHost' }],
    },
    // 业务代码 import primevue/toast
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Toast from 'primevue/toast'</script>",
      errors: [{ messageId: 'primeToastImport' }],
    },
    // 业务代码 import primevue/usetoast
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import { useToast } from 'primevue/usetoast'</script>",
      errors: [{ messageId: 'primeToastImport' }],
    },
    // 多处命中：模板 + import 各一处
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Toast from 'primevue/toast'</script><template><Toast /></template>",
      errors: [{ messageId: 'primeToastImport' }, { messageId: 'rawToastHost' }],
    },
  ],
})
