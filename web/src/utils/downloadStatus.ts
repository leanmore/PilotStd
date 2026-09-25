// web/src/utils/downloadStatus.ts
// 下载状态展示映射 —— 收藏页与公告详情页的**唯一事实源**
//
// 事实来源：`favorite_downloads.status`。后端只写 6 个值
// （pending/downloading/archiving/done/failed/abandoned），表定义无 CHECK 约束，
// 因此未知值必须兜底（显示原文，绝不空白）。
// 另有第 7 个**纯前端兜底**展示项：收藏已存在但队列行缺失（download_status === null）
// → 显示"未加入队列"（历史遗留行：2026-08-23 前的收藏创建路径不建队列行，见技术债 #18）。
// 它不在数据库枚举内，必须在界面上可解释而非留空；措辞刻意区别于"排队中"，
// 因为这类行不会自动流转，说"待下载"会误导。

export type DownloadStatus = 'pending' | 'downloading' | 'archiving' | 'done' | 'failed' | 'abandoned'

/** 数据库枚举（6 值全集）→ i18n 叶子键；纯前端兜底项见 NOT_QUEUED_LABEL_KEY */
export const DOWNLOAD_STATUS_LABEL_KEYS: Record<DownloadStatus, string> = {
  pending: 'download.status.pending',
  downloading: 'download.status.downloading',
  archiving: 'download.status.archiving',
  done: 'download.status.done',
  failed: 'download.status.failed',
  abandoned: 'download.status.abandoned',
}

/** 颜色语义分级：完成绿 / 进行中蓝 / 待处理灰 / 可重试失败橙 / 终态放弃红 / 未知灰 */
export const DOWNLOAD_STATUS_SEVERITY: Record<DownloadStatus, string> = {
  done: 'success',
  downloading: 'info',
  archiving: 'info',
  pending: 'secondary',
  failed: 'warn',
  abandoned: 'danger',
}

/** 纯前端兜底项：已收藏但没有队列行（download_status === null，历史遗留） */
export const NOT_QUEUED_LABEL_KEY = 'download.status.notQueued'

/** 未知枚举值的兜底颜色 */
export const UNKNOWN_SEVERITY = 'secondary'

/** Tooltip / 展示用错误文本截断长度（API 返回全量，展示层截断） */
export const ERROR_DISPLAY_MAX_CHARS = 120

/** 状态 → i18n 标签键；null/undefined（无队列行）→ "未加入队列"；未知值 → 空串（由调用方回退原文） */
export function downloadStatusLabelKey(status: string | null | undefined): string {
  if (!status) return NOT_QUEUED_LABEL_KEY
  return DOWNLOAD_STATUS_LABEL_KEYS[status as DownloadStatus] || ''
}

/** 状态 → 颜色分级；null 与未知值都走灰色 */
export function downloadStatusSeverity(status: string | null | undefined): string {
  if (!status) return UNKNOWN_SEVERITY
  return DOWNLOAD_STATUS_SEVERITY[status as DownloadStatus] || UNKNOWN_SEVERITY
}

/** 状态 → 展示文案：优先 i18n，未知枚举值回退原文（保证任何取值都不空白） */
export function downloadStatusLabel(status: string | null | undefined, t: (key: string) => string): string {
  const key = downloadStatusLabelKey(status)
  return key ? t(key) : String(status)
}

/** 错误文本截断（API 全量、展示截断；悬停由 title 提供全量） */
export function truncateError(error: string | null | undefined): string {
  if (!error) return ''
  return error.length > ERROR_DISPLAY_MAX_CHARS ? `${error.slice(0, ERROR_DISPLAY_MAX_CHARS)}…` : error
}

/**
 * 收藏判定：**只看后端是否返回了收藏对象**（未收藏 / 他人不可见 → null）。
 *
 * 为什么不用状态枚举判定（旧实现按 done/pending/downloading/archiving 白名单）：
 * 收藏状态与下载状态是两件事——下载 failed/abandoned 的收藏依然是**有效收藏**，
 * 旧实现会把它们显示成"未收藏"（星标空心），用户点一下变成重复收藏。
 * 用 `!= null` 而非 `!== null`：batch-status 若缺键返回 undefined 也视为未收藏。
 */
export function isFavorited(statusResponse: unknown): boolean {
  return statusResponse != null
}

/** 下载状态标签的悬停提示：最后尝试时间 + 失败原因（全量） */
export function downloadTooltip(
  status: { last_attempt?: string | null; download_error?: string | null },
  t: (key: string) => string,
): string {
  const parts: string[] = []
  if (status.last_attempt) parts.push(`${t('download.status.lastAttempt')}: ${status.last_attempt}`)
  if (status.download_error) parts.push(status.download_error)
  return parts.join('\n')
}
