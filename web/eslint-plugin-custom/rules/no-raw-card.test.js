// no-raw-card 规则单测（2026-11-22 DS 阶段三 · 模块三）
import { RuleTester } from 'eslint'
import vueParser from 'vue-eslint-parser'

import rule from './no-raw-card.js'

const rt = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    parser: vueParser,
  },
})

rt.run('no-raw-card', rule, {
  valid: [
    // AppCard 封装自身允许用 PrimeVue Card（封装点）
    {
      filename: 'src/components/ui/AppCard.vue',
      code: '<template><Card><template #content>x</template></Card></template>',
    },
    // 业务代码用 AppCard：合法
    {
      filename: 'src/views/Foo.vue',
      code: '<template><AppCard><template #content>x</template></AppCard></template>',
    },
    // 测试文件豁免
    {
      filename: 'src/views/Foo.test.ts',
      code: "import Card from 'primevue/card'",
    },
    // e2e 豁免
    {
      filename: 'web/e2e/foo.spec.ts',
      code: "import Card from 'primevue/card'",
    },
    // main.ts 是 PrimeVue 全局注册点
    {
      filename: 'src/main.ts',
      code: "import Card from 'primevue/card'",
    },
  ],
  invalid: [
    // PrimeVue <Card>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><Card><template #content>x</template></Card></template>',
      errors: [{ messageId: 'primeCard' }],
    },
    // Prime 前缀别名
    {
      filename: 'src/views/Foo.vue',
      code: '<template><PrimeCard /></template>',
      errors: [{ messageId: 'primeCard' }],
    },
    // 脚本里 import PrimeVue Card
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Card from 'primevue/card'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    // 多处命中：模板 + import 各一处
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Card from 'primevue/card'</script><template><Card /></template>",
      errors: [{ messageId: 'primeImport' }, { messageId: 'primeCard' }],
    },
  ],
})
