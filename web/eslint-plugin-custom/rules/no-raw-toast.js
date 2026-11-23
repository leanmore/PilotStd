// custom/no-raw-toast.js
// DS 门禁：业务代码必须通过 `useAppToast()` / `appToast` 发提示，禁止直接用 PrimeVue Toast。
//
// 阶段三（2026-11-23）：以 warn 落地并统计存量；替换完成后升 error。
// 豁免：App* 封装自身（src/components/ui/App*.vue）、App.vue（宿主与全局绑定）、
//       src/main.ts、测试文件、e2e。
//
// 实现要点（实测，与 no-raw-button / no-raw-input / no-raw-table / no-raw-card 完全一致）：
// ESLint 10 + vue-eslint-parser 下直接写 `VElement` 访问器不会触发；
// 必须经 eslint-plugin-vue 的 `defineTemplateBodyVisitor` 才能遍历模板。
// 该包只提供 `dist/index.js`（无 `lib/utils` 子路径）；其 utils 是 CommonJS，
// ESM 命名导入拿不到函数（实测 undefined），故用默认导入再解构。

import vueUtils from 'eslint-plugin-vue/dist/utils/index.js'

// CJS 双层 default：函数挂在 vueUtils.default 上（实测 Object.keys 只有 'default'）
const { defineTemplateBodyVisitor } = vueUtils.default

// 模板侧禁止的组件名（含 Prime 前缀别名）
const RAW_TOAST_TAGS = {
  Toast: 'rawToastHost',
  PrimeToast: 'rawToastHost',
}

// 脚本侧禁止直接 import 的入口
const PRIME_MODULES = new Set(['primevue/toast', 'primevue/usetoast'])

// DS 封装点与宿主绑定处（这两处**必须**直接接触 PrimeVue 原语，否则封装不成立）
const ALLOWED_FILES = [
  'src/main.ts', // PrimeVue 全局注册点
  'src/App.vue', // Toast 宿主挂载 + bindAppToast 注入
]

function isAllowed(filename) {
  const norm = filename.replace(/\\/g, '/')
  // src/components/ui/App*.vue —— AppToast 等封装点
  if (/(^|\/)components\/ui\/App[^/]*\.vue$/.test(norm)) return true
  // composables/useAppToast.ts 是唯一的服务封装点
  if (/(^|\/)composables\/useAppToast\.ts$/.test(norm)) return true
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
        '业务代码禁止直接使用 PrimeVue Toast（<Toast /> 或 useToast()），' +
        '必须通过 useAppToast() / appToast 发提示（见 docs/reference/ui-system.md 十四）。',
    },
    schema: [],
    messages: {
      rawToastHost:
        '禁止直接使用 PrimeVue <Toast />：宿主已由 App.vue 的 <AppToast /> 统一挂载，' +
        '发提示请用 useAppToast() / appToast（docs/reference/ui-system.md 十四）。',
      primeToastImport:
        '禁止直接 import PrimeVue Toast（{{source}}）：请改用 useAppToast() / appToast' +
        '（severity/life/closable 口径已收口，见 docs/reference/ui-system.md 十四）。',
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
          const messageId = RAW_TOAST_TAGS[raw]
          if (messageId) {
            context.report({ node, messageId })
          }
        },
      },
      {
        ImportDeclaration(node) {
          const src = node.source?.value
          if (typeof src === 'string' && PRIME_MODULES.has(src)) {
            context.report({ node, messageId: 'primeToastImport', data: { source: src } })
          }
        },
      },
    )
  },
}
