// eslint-plugin-custom/rules/no-raw-i18n-key.js
// 禁止将 *Key 字段直接赋值给变量或模板，必须经 t() 包装
module.exports = {
  meta: {
    type: 'problem',
    docs: { description: '禁止将 *Key 字段直接赋值给变量或模板，必须经 t() 包装' },
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
