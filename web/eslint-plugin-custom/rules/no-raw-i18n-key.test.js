// no-raw-i18n-key 规则单测（2026-10-25 B1：区分"存键定义"与"裸传"）
import { RuleTester } from 'eslint'

import rule from './no-raw-i18n-key.js'

const rt = new RuleTester({
  languageOptions: { ecmaVersion: 2022, sourceType: 'module' },
})

rt.run('no-raw-i18n-key', rule, {
  valid: [
    // 键定义表：渲染处 t(item.labelKey)
    { code: "const X = { labelKey: 'nav.home' }" },
    // 返回对象（composable 暴露 computed/函数名）
    { code: 'function f() { return { parseStatusLabelKey } }' },
    // 解构取键名
    { code: 'const { labelKey } = props' },
    // 数组定义表
    { code: "const T = [{ labelKey: 'a.b' }]" },
    // 箭头函数返回的对象字面量
    { code: "const m = () => ({ labelKey: 'a.b' })" },
    // 数组定义写入（push 到响应式数组）
    { code: "layout.value.push({ titleKey: 'a.b' })" },
    // ref([...]) 声明包装（ref 为直接 import 的 Identifier）
    { code: "const s = ref([{ labelKey: 'a.b' }])" },
    // 成员访问：t() 消费
    { code: 't(item.labelKey)' },
  ],
  invalid: [
    // 对象字面量直接作为调用参数：可能被当作已翻译文本消费
    {
      code: "foo({ labelKey: 'a.b' })",
      errors: [{ message: /禁止裸传/ }],
    },
    // 调用结果赋给变量但非 ref 包装：仍应报告（防止 VariableDeclarator 宽泛豁免）
    {
      code: "const x = foo({ labelKey: 'a.b' })",
      errors: [{ message: /禁止裸传/ }],
    },
  ],
})
