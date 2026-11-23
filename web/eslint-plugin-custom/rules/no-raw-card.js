// custom/no-raw-card.js
// DS 门禁：业务代码的卡片容器必须使用 <AppCard>，禁止直接使用 PrimeVue <Card>。
//
// 阶段三（2026-11-22）：以 warn 落地并统计存量；分批替换完成后升 error。
// 豁免：App* 封装自身（src/components/ui/App*.vue）、PrimeVue 全局注册点（src/main.ts）、
//       测试文件、e2e。
//
// 实现要点（实测，与 no-raw-button.js / no-raw-input.js / no-raw-table.js 完全一致）：
// ESLint 10 + vue-eslint-parser 下直接写 `VElement` 访问器不会触发；
// 必须经 eslint-plugin-vue 的 `defineTemplateBodyVisitor` 才能遍历模板。
// 该包只提供 `dist/index.js`（无 `lib/utils` 子路径）；其 utils 是 CommonJS，
// ESM 命名导入拿不到函数（实测 undefined），故用默认导入再解构。

import vueUtils from 'eslint-plugin-vue/dist/utils/index.js'

// CJS 双层 default：函数挂在 vueUtils.default 上（实测 Object.keys 只有 'default'）
const { defineTemplateBodyVisitor } = vueUtils.default

// PrimeVue 卡片组件名 → messageId（含 Prime 前缀别名）
const PRIME_CARD_TAGS = {
  Card: 'primeCard',
  PrimeCard: 'primeCard',
}

// 脚本侧禁止直接 import 的 PrimeVue 入口
const PRIME_MODULES = new Set(['primevue/card'])

// DS 封装点：AppCard 内部允许用 PrimeVue 原语（样式与行为在封装内收口）
const ALLOWED_FILES = ['src/main.ts']

function isAllowed(filename) {
  const norm = filename.replace(/\\/g, '/')
  // src/components/ui/App*.vue —— AppCard/AppTable/AppDialog/... 的封装点
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
        '业务代码禁止直接使用 PrimeVue <Card>，必须使用 <AppCard>' +
        '（见 docs/reference/ui-system.md 十三）。',
    },
    schema: [],
    messages: {
      primeCard:
        '禁止直接使用 PrimeVue <Card>：请改用 <AppCard>（阴影/圆角/内边距由 DS 统一，' +
        '见 docs/reference/ui-system.md 十三）。需要完全自定义卡片结构时用 <AppCard bare>。',
      primeImport:
        '禁止直接 import PrimeVue Card（{{source}}）：请改用 <AppCard>' +
        '（docs/reference/ui-system.md 十三）。',
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
          const messageId = PRIME_CARD_TAGS[raw]
          if (messageId) {
            context.report({ node, messageId })
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
