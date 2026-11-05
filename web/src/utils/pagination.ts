// 列表分页的每页条数选项与切换逻辑（公告/任务历史共用，便于单测）
export const ANNOUNCE_PAGE_SIZES: number[] = [25, 50, 100]
export const TASK_HISTORY_PAGE_SIZES: number[] = [10, 50, 100]

/** 分页事件里的 rows 合法时采用，否则保持当前值（防 PrimeVue 传 undefined）。 */
export function resolveRows(
  eventRows: number | undefined,
  currentRows: number,
  allowed: readonly number[],
): number {
  return eventRows !== undefined && allowed.includes(eventRows) ? eventRows : currentRows
}
