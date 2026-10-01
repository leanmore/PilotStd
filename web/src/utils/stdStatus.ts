// web/src/utils/stdStatus.ts
// 标准状态（后端 `pilotstd/core/status.py`）在前端的**唯一事实源**。
//
// 契约（#32-C / R14-4c，2026-10-01）：
//   后端响应在原有 `status`（数据值，中文，**向后兼容**）之外同时给出 `status_key`
//   （稳定英文键：active/upcoming/withdrawn/superseded/voided/expired/pending/unknown）。
//   前端**一律比较 status_key**，不再比较中文文案 —— 这样状态判定与界面语言彻底解耦，
//   改文案不会静默破坏逻辑（原先 13 处中文比较需 `i18n-allow` 豁免，现已全部消除）。
//
// 注意：本文件只做**语义分级**（颜色/归属），不产出任何用户可见文案，
// 因此不需要 i18n key；状态文案仍由 locales 的既有键族提供。

export type StandardStatusKey =
  | 'active'
  | 'upcoming'
  | 'withdrawn'
  | 'superseded'
  | 'voided'
  | 'expired'
  | 'pending'
  | 'unknown'

/** 状态键 → 颜色语义分级（与后端语义一致：现行绿 / 废止族红 / 待确认黄 / 即将实施蓝 / 未知灰） */
export const STD_STATUS_SEVERITY: Record<StandardStatusKey, string> = {
  active: 'success',
  upcoming: 'info',
  withdrawn: 'danger',
  superseded: 'danger',
  voided: 'danger',
  expired: 'danger',
  pending: 'warn',
  unknown: 'secondary',
}

/** 废止族状态键（等价于后端 `ABOLISHED_STATUSES_WITH_EXPIRED`） */
export const ABOLISHED_STATUS_KEYS: readonly StandardStatusKey[] = [
  'withdrawn',
  'superseded',
  'voided',
  'expired',
]

/** 未知/缺失键的兜底颜色（与改造前各视图的兜底保持一致：默认灰） */
export const STD_STATUS_FALLBACK_SEVERITY = 'secondary'

/** 状态键 → 颜色语义；未知键回退 `fallback`（调用方可传入本视图原有的兜底色） */
export function severityOfStatusKey(key?: string | null, fallback: string = STD_STATUS_FALLBACK_SEVERITY): string {
  if (!key) return fallback
  return STD_STATUS_SEVERITY[key as StandardStatusKey] ?? fallback
}

/** 是否为现行（active）—— 供只需区分"现行/其它"的视图使用 */
export function isActiveStatusKey(key?: string | null): boolean {
  return key === 'active'
}

/** 是否为废止族状态键 */
export function isAbolishedStatusKey(key?: string | null): boolean {
  return !!key && ABOLISHED_STATUS_KEYS.includes(key as StandardStatusKey)
}

/**
 * 状态筛选下拉提交给后端的值：**英文键**（后端 `resolve_status_filter` 同时接受
 * 英文键与历史中文值，故老书签里的中文过滤参数仍然有效）。
 */
export const STD_STATUS_FILTER = {
  current: 'active',
  abolished: 'withdrawn',
  unknown: 'unknown',
} as const
