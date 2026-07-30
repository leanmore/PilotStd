// eslint-plugin-custom/rules/no-sensitive-persist.js
// Pinia 持久化白名单检查：禁止全量持久化或持久化敏感字段
const SENSITIVE_FIELDS = ['role', 'permission', 'token', 'accessToken', 'refreshToken'];

module.exports = {
  meta: { type: 'problem', schema: [] },
  create(context) {
    return {
      Property(node) {
        if (node.key?.name !== 'paths') return;

        // 检测 paths: true 全量持久化
        if (node.value?.type === 'Literal' && node.value.value === true) {
          context.report({
            node,
            message: 'Pinia 持久化禁止使用 paths: true，必须显式声明白名单',
          });
          return;
        }

        // 检测白名单中包含敏感字段
        if (node.value?.type === 'ArrayExpression') {
          node.value.elements.forEach(el => {
            if (el?.type === 'Literal' && SENSITIVE_FIELDS.includes(el.value)) {
              context.report({
                node: el,
                message: `敏感字段 '${el.value}' 禁止持久化到客户端存储，请通过 API 恢复`,
              });
            }
          });
        }
      },
    };
  },
};
