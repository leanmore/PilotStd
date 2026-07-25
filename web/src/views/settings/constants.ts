/**
 * Settings Tab 常量
 *
 * TODO(P2-FOLLOWUP): 后续改为 data-tab 名称定位，彻底消除 DOM 顺序依赖。
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
