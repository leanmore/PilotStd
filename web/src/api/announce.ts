// web/src/api/announce.ts — 公告抓取与结果读取
import http from './http'
import type { RouteTag } from '../types/route-tag'
import type { PaginatedResult } from '../composables/useIncrementalScroll'
import type {
  AnnounceResponse,
  SuccessResponse,
  AnnouncementDetail,
  AnnouncementRecord,
} from '../types/api'

export const getAnnounceResults = (sourceSite?: string, fromDate?: string, routeTag?: RouteTag): Promise<AnnounceResponse> =>
  http.get('/announce/results', { params: { source_site: sourceSite || '', from_date: fromDate || '' }, routeTag }).then(r => r.data)

export const postAnnounceCheck = (sinceDate?: string, types?: string): Promise<SuccessResponse> =>
  http.post('/announce/check', null, { params: { ...(sinceDate ? { since_date: sinceDate } : {}), ...(types ? { types } : {}) } }).then(r => r.data)

// ── Phase 3: 公告详情 ──────────────────────────────────

/** 旧格式兼容：通过 announce_no 查询所有来源的公告 */
export const getAnnouncementByNo = (announceNo: string, routeTag?: RouteTag): Promise<Array<{ source_site: string; announce_no: string; title: string }>> =>
  http.get(`/announcements/by-no/${encodeURIComponent(announceNo)}`, { routeTag }).then(r => r.data)
export const getAnnouncementDetail = (announceNo: string, source?: string): Promise<AnnouncementDetail> => {
  const params = source ? { source } : {}
  return http.get(`/announcements/${encodeURIComponent(announceNo)}`, { params }).then(r => r.data)
}

/** 轻量版详情：records 不含 confidence/source_type/created_at/updated_at，响应体缩减约 40% */
export const getAnnounceDetailLite = (announceNo: string, source?: string, routeTag?: RouteTag): Promise<AnnouncementDetail> => {
  const params = source ? { source } : {}
  return http.get(`/announcements/${encodeURIComponent(announceNo)}/lite`, { params, routeTag }).then(r => r.data)
}

/** 分页获取公告记录（Phase 1 分页端点，排序 standard_number ASC） */
export const getAnnounceRecords = (announceNo: string, page: number, pageSize: number): Promise<PaginatedResult> =>
  http.get(`/announcements/${encodeURIComponent(announceNo)}/records`, {
    params: { page, page_size: pageSize },
  }).then(r => r.data)

/** 触发附件解析 */
export const triggerParse = (announceNo: string): Promise<{ status: string }> =>
  http.post(`/announcements/${announceNo}/parse`).then(r => r.data)

/** 获取解析状态 */
export const getParseStatus = (announceNo: string): Promise<{ status: string; record_count?: number }> =>
  http.get(`/announcements/${announceNo}/parse-status`).then(r => r.data)

/** 单行更新（单元格编辑） */
export const updateRecord = (id: number, data: Partial<AnnouncementRecord>): Promise<{ status: string }> =>
  http.patch(`/announcement-record/${id}`, data).then(r => r.data)

/** 批量确认入库 */
export const batchApprove = (ids: number[]): Promise<{ approved_count: number }> =>
  http.post('/announcement-record/batch-approve', { ids }).then(r => r.data)

// ── Phase 4a: 收藏 ──────────────────────────────────────
//
// 下载状态字段（download_status/download_error/last_attempt/download_updated_at）：
// 来源 favorite_downloads，列表与批量接口同名同义；download_status 为 null 表示
// "收藏存在但队列行缺失"（展示层显示"未加入队列"）。枚举取值见 @/utils/downloadStatus。
//
// 单条 `getFavoriteStatus`（GET /favorites/{id}/status）已于第三轮 #16 移除（全库零
// 消费方，且对"收藏但无队列行"与"未收藏"返回同一份 null 体）；后端端点在第七轮 #19
// 依据现场日志（零仓外调用方）一并删除，故此处不再保留该函数的说明注释。

/** 下载状态四字段（列表 / 批量接口共用口径） */
export interface FavoriteDownloadFields {
  download_status: string | null
  download_error: string | null
  last_attempt: string | null
  download_updated_at: string | null
}

/** 批量状态返回的单条收藏对象（null = 未收藏 / 他人不可见） */
export interface BatchFavoriteStatus extends FavoriteDownloadFields {
  favorite_id: number
  status: string
}

export const addFavorite = (recordId: number): Promise<{ status: string; favorite_id: number }> =>
  http.post('/favorites', { record_id: recordId }).then(r => r.data)

export const getBatchFavoriteStatus = (
  recordIds: number[],
): Promise<{ statuses: Record<string, BatchFavoriteStatus | null> }> =>
  http.post('/favorites/batch-status', { record_ids: recordIds }).then(r => r.data)

export const removeFavorite = (recordId: number): Promise<{ status: string }> =>
  http.delete(`/favorites/${recordId}`).then(r => r.data)

export const listFavorites = (params?: { status?: string }): Promise<{ favorites: any[] }> =>
  http.get('/favorites', { params }).then(r => r.data)
