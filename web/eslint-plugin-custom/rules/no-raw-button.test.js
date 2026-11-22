// no-raw-button 规则单测（2026-11-22 DS 阶段一）
import { RuleTester } from 'eslint'
import vueParser from 'vue-eslint-parser'

import rule from './no-raw-button.js'

const rt = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    parser: vueParser,
  },
})

rt.run('no-raw-button', rule, {
  valid: [
    // AppButton 自身允许用原生 button（封装点）
    {
      filename: 'src/components/ui/AppButton.vue',
      code: '<template><button type="button" /></template>',
    },
    // 业务代码用 AppButton：合法
    {
      filename: 'src/views/Foo.vue',
      code: '<template><AppButton type="primary" label="x" /></template>',
    },
    // 测试文件豁免
    {
      filename: 'src/views/Foo.test.ts',
      code: "import Button from 'primevue/button'",
    },
  ],
  invalid: [
    // 原生 <button>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><button type="button">x</button></template>',
      errors: [{ messageId: 'rawButton' }],
    },
    // PrimeVue <Button>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><Button label="x" /></template>',
      errors: [{ messageId: 'primeButton' }],
    },
    // 脚本里 import PrimeVue Button
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Button from 'primevue/button'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
  ],
})
