// custom/no-raw-button.js
// DS 门禁：业务代码必须使用 <AppButton>，禁止原生 <button> 与 PrimeVue <Button>。
//
// 阶段一（2026-11-22）：以 warn 落地并统计存量；分批替换完成后升 error。
// 豁免：AppButton 自身、测试文件、e2e。
//
// 实现要点（实测）：ESLint 10 + vue-eslint-parser 下直接写 `VElement` 访问器不会触发；
// 必须经 eslint-plugin-vue 的 `defineTemplateBodyVisitor` 才能遍历模板。
// 该包只提供 `dist/index.js`（无 `lib/utils` 子路径）；其 utils 是 CommonJS，
// ESM 命名导入拿不到函数（实测 undefined），故用默认导入再解构。

import vueUtils from 'eslint-plugin-vue/dist/utils/index.js'

// CJS 双层 default：函数挂在 vueUtils.default 上（实测 Object.keys 只有 'default'）
const { defineTemplateBodyVisitor } = vueUtils.default

const ALLOWED_FILES = ['src/components/ui/AppButton.vue']

function isAllowed(filename) {
  const norm = filename.replace(/\\/g, '/')
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
        '业务代码禁止直接使用原生 <button> 或 PrimeVue <Button>，必须使用 <AppButton>（见 docs/reference/ui-system.md）。',
    },
    schema: [],
    messages: {
      rawButton: '禁止原生 <button>：请改用 <AppButton type="primary|secondary|danger|ghost">（docs/reference/ui-system.md）。',
      primeButton: '禁止直接使用 PrimeVue <Button>：请改用 <AppButton>（docs/reference/ui-system.md）。',
      primeImport: '禁止直接 import PrimeVue Button：请改用 <AppButton>（docs/reference/ui-system.md）。',
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
          if (raw === 'button') {
            context.report({ node, messageId: 'rawButton' })
          } else if (raw === 'Button' || raw === 'PrimeButton') {
            context.report({ node, messageId: 'primeButton' })
          }
        },
      },
      {
        ImportDeclaration(node) {
          const src = node.source?.value
          if (typeof src === 'string' && src === 'primevue/button') {
            context.report({ node, messageId: 'primeImport' })
          }
        },
      },
    )
  },
}
