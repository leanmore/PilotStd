/**
 * Settings Tab 常量
 *
 * TODO(A-10): 改 data-tab 名称定位，消除 DOM 顺序依赖（见 docs/debt/03-open.md）。
 *   示例: wrapper.find('[data-tab="storage"]') 替代 findAll('.tab-bar button')[0]
 */
export const SETTINGS_TAB_KEYS = [
  'storage',
  'network',
  'query',
  'scan',
  'tasks',
  'ui',
  'ocr',
  'sites',
  'users',
  'token',
  'notification',
  'validity',
  'system',
] as const
