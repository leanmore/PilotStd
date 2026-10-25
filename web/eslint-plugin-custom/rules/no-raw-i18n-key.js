// eslint-plugin-custom/rules/no-raw-i18n-key.js
// 禁止把 *Key 字段当"已翻译文本"裸传；键存放在配置表/返回对象里（渲染处再 t()）是合法形态。
//
// ⚠️ 命名避坑指南：若变量/prop 语义与 i18n 无关，避免以 Key 结尾：
//   计数器/触发器 → refreshCount / triggerId
//   对象查找标识 → tabId / schemaTabName / activeTab
//   缓存键       → cacheId（而非 cacheKey）
// 确需保留 Key 后缀时，加 eslint-disable-next-line 并附语义说明。
//
// 覆盖边界（2026-10-25）：本规则只能看见**脚本内的 Property 节点**；
// 模板里的裸传（`{{ item.labelKey }}`）不在 AST 范围，由人工评审兜底
// （G-040 只查中文字面量，不查键名裸传）。
const DEFINITION_PARENTS = new Set([
  'VariableDeclarator',
  'ReturnStatement',
  'ArrayExpression',
  'ArrowFunctionExpression',
  'AssignmentExpression',
  'ExportDefaultDeclaration',
])

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        '禁止将 *Key 字段直接赋值给变量或模板，必须经 t() 包装。' +
        '命名约定：非 i18n 语义的变量避免以 Key 结尾（用 refreshCount/tabId/schemaTabName 替代）。',
    },
    schema: [],
  },
  create(context) {
    return {
      Property(node) {
        const keyName = node.key?.name || node.key?.value
        // 计算属性/字面量键的 value 可能是数字或对象（ESLint 10 的 AST 形态），先判类型
        if (typeof keyName !== 'string' || !keyName.endsWith('Key')) return

        // 解构取键名（const { labelKey } = props）不是裸传
        if (node.parent?.type === 'ObjectPattern') return

        // 定义表：const T = { labelKey: 'x' } / return { xKey } / [{ labelKey }] / () => ({ labelKey })
        // 支持嵌套对象（Record 的值对象）与 ref([...]) 这类声明包装，一路向上找到容器外的祖先
        let cur = node.parent
        while (
          cur &&
          [
            'ObjectExpression',
            'Property',
            'ArrayExpression',
            'TSAsExpression',
            'TSNonNullExpression',
          ].includes(cur.type)
        ) {
          cur = cur.parent
        }
        if (cur?.type === 'CallExpression') {
          const callee = cur.callee
          const calleeName = callee?.property?.name || callee?.name
          // 数组定义写入（layout.value.push({ titleKey })）：键随后由模板 t() 消费
          if (['push', 'unshift', 'splice'].includes(calleeName)) return
          // 仅跳过 `const x = ref([...])` 这一具体包装（ref 为直接 import 的 Identifier）；
          // `const x = foo({ labelKey })` 仍按"调用参数对象"报告
          if (
            cur.parent?.type === 'VariableDeclarator' &&
            callee?.type === 'Identifier' &&
            callee.name === 'ref'
          ) {
            return
          }
        }
        if (cur && DEFINITION_PARENTS.has(cur.type)) return

        const parent = node.parent?.parent
        const isWrapped =
          parent?.type === 'CallExpression' &&
          ['t', '$t', 'tr'].includes(parent.callee?.name || parent.callee?.property?.name)

        if (!isWrapped) {
          context.report({
            node,
            message: `'${keyName}' 是 i18n 键名，必须通过 t() 翻译后使用，禁止裸传`,
          })
        }
      },
    }
  },
}
