// no-raw-input 规则单测（2026-11-22 DS 阶段三）
import { RuleTester } from 'eslint'
import vueParser from 'vue-eslint-parser'

import rule from './no-raw-input.js'

const rt = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    parser: vueParser,
  },
})

rt.run('no-raw-input', rule, {
  valid: [
    // 业务代码用 AppInput：合法
    {
      filename: 'src/views/Foo.vue',
      code: '<template><AppInput v-model="name" size="m" placeholder="x" /></template>',
    },
    // App* 封装点内部允许用原生标签（封装点）
    {
      filename: 'src/components/ui/AppInput.vue',
      code: '<template><input class="p-inputtext" :value="modelValue" /></template>',
    },
    // App* 封装点内部允许结构性 type="file"
    {
      filename: 'src/components/ui/AppInput.vue',
      code: '<template><input type="file" @change="onChange" /></template>',
    },
    // App* 封装点内部允许 PrimeVue 原语 + 直接 import
    {
      filename: 'src/components/ui/AppSelect.vue',
      code: "<script setup>import Select from 'primevue/select'</script><template><Select :options=\"[]\" /></template>",
    },
    // 测试文件豁免（fixture/断言目标）
    {
      filename: 'src/views/Foo.test.ts',
      code: "import InputText from 'primevue/inputtext'",
    },
    // e2e 豁免
    {
      filename: 'src/e2e/login.spec.ts',
      code: "import Select from 'primevue/select'",
    },
    // PrimeVue 全局注册点豁免
    {
      filename: 'src/main.ts',
      code: "import InputText from 'primevue/inputtext'",
    },
    // 非输入类 PrimeVue 组件不拦
    {
      filename: 'src/views/Foo.vue',
      code: '<template><DataTable :value="rows" /></template>',
    },
  ],
  invalid: [
    // 原生 <input>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><input v-model="name" class="fi" /></template>',
      errors: [{ messageId: 'rawInput' }],
    },
    // 原生 <select>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><select v-model="theme"><option value="light">light</option></select></template>',
      errors: [{ messageId: 'rawSelect' }],
    },
    // 原生 <textarea>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><textarea v-model="text" rows="4" /></template>',
      errors: [{ messageId: 'rawTextarea' }],
    },
    // PrimeVue <InputText>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><InputText v-model="name" /></template>',
      errors: [{ messageId: 'primeInputText' }],
    },
    // PrimeVue <Select>
    {
      filename: 'src/views/Foo.vue',
      code: '<template><Select v-model="theme" :options="themes" /></template>',
      errors: [{ messageId: 'primeSelect' }],
    },
    // PrimeVue <Dropdown>（旧别名，同样拦）
    {
      filename: 'src/views/Foo.vue',
      code: '<template><Dropdown v-model="theme" :options="themes" /></template>',
      errors: [{ messageId: 'primeSelect' }],
    },
    // PrimeVue <Checkbox> / <ToggleSwitch> / <DatePicker> / <InputNumber> / <Password> / <Textarea> / <SelectButton>
    {
      filename: 'src/components/Foo.vue',
      code: '<template><Checkbox v-model="on" binary /></template>',
      errors: [{ messageId: 'primeCheckbox' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: '<template><ToggleSwitch v-model="on" /></template>',
      errors: [{ messageId: 'primeToggleSwitch' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: '<template><DatePicker v-model="date" /></template>',
      errors: [{ messageId: 'primeDatePicker' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: '<template><InputNumber v-model="n" /></template>',
      errors: [{ messageId: 'primeInputNumber' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: '<template><Password v-model="p" toggleMask /></template>',
      errors: [{ messageId: 'primePassword' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: '<template><Textarea v-model="t" rows="3" /></template>',
      errors: [{ messageId: 'primeTextarea' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: '<template><SelectButton v-model="mode" :options="modes" /></template>',
      errors: [{ messageId: 'primeSelectButton' }],
    },
    // 脚本里 import PrimeVue 输入组件
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import InputText from 'primevue/inputtext'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    {
      filename: 'src/views/Foo.vue',
      code: "<script setup>import Select from 'primevue/select'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: "<script setup>import ToggleSwitch from 'primevue/toggleswitch'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    {
      filename: 'src/components/Foo.vue',
      code: "<script setup>import DatePicker from 'primevue/datepicker'</script>",
      errors: [{ messageId: 'primeImport' }],
    },
    // 同一文件多命中：按控件逐条报
    {
      filename: 'src/views/Foo.vue',
      code: '<template><input v-model="a" /><select v-model="b" /></template>',
      errors: [{ messageId: 'rawInput' }, { messageId: 'rawSelect' }],
    },
  ],
})
