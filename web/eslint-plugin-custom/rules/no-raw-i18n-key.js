// eslint-plugin-custom/rules/no-raw-i18n-key.js
// 禁止将 *Key 字段直接赋值给变量或模板，必须经 t() 包装
//
// ⚠️ 命名避坑指南：若变量/prop 语义与 i18n 无关，避免以 Key 结尾：
//   计数器/触发器 → refreshCount / triggerId
//   对象查找标识 → tabId / schemaTabName / activeTab
//   缓存键       → cacheId（而非 cacheKey）
// 确需保留 Key 后缀时，加 eslint-disable-next-line 并附语义说明。
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
        const keyName = node.key?.name || node.key?.value;
        if (!keyName || !keyName.endsWith('Key')) return;

        const parent = node.parent?.parent;
        const isWrapped =
          parent?.type === 'CallExpression' &&
          ['t', '$t', 'tr'].includes(parent.callee?.name || parent.callee?.property?.name);

        if (!isWrapped) {
          context.report({
            node,
            message: `'${keyName}' 是 i18n 键名，必须通过 t() 翻译后使用，禁止裸传`,
          });
        }
      },
    };
  },
};
