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

export const getAnnounceResults = async (sourceSite?: string, fromDate?: string, routeTag?: RouteTag): Promise<AnnounceResponse> =>
  (await http.get('/announce/results', { params: { source_site: sourceSite || '', from_date: fromDate || '' }, routeTag })).data

export const postAnnounceCheck = async (sinceDate?: string, types?: string): Promise<SuccessResponse> =>
  (await http.post('/announce/check', null, { params: { ...(sinceDate ? { since_date: sinceDate } : {}), ...(types ? { types } : {}) } })).data

// ── Phase 3: 公告详情 ──────────────────────────────────

/** 旧格式兼容：通过 announce_no 查询所有来源的公告 */
export const getAnnouncementByNo = async (announceNo: string, routeTag?: RouteTag): Promise<Array<{ source_site: string; announce_no: string; title: string }>> =>
  (await http.get(`/announcements/by-no/${encodeURIComponent(announceNo)}`, { routeTag })).data
export const getAnnouncementDetail = async (announceNo: string, source?: string): Promise<AnnouncementDetail> => {
  const params = source ? { source } : {}
  return (await http.get(`/announcements/${encodeURIComponent(announceNo)}`, { params })).data
}

/** 轻量版详情：records 不含 confidence/source_type/created_at/updated_at，响应体缩减约 40% */
export const getAnnounceDetailLite = async (announceNo: string, source?: string, routeTag?: RouteTag): Promise<AnnouncementDetail> => {
  const params = source ? { source } : {}
  return (await http.get(`/announcements/${encodeURIComponent(announceNo)}/lite`, { params, routeTag })).data
}

/** 分页获取公告记录（Phase 1 分页端点，排序 standard_number ASC） */
export const getAnnounceRecords = async (announceNo: string, page: number, pageSize: number, source?: string): Promise<PaginatedResult> =>
  (await http.get(`/announcements/${encodeURIComponent(announceNo)}/records`, {
    params: { page, page_size: pageSize, ...(source ? { source } : {}) },
  })).data

/** 触发附件解析 */
export const triggerParse = async (announceNo: string, source?: string): Promise<{ status: string }> =>
  (await http.post(`/announcements/${announceNo}/parse`, null, { params: source ? { source } : {} })).data

/** 获取解析状态 */
export const getParseStatus = async (announceNo: string, source?: string): Promise<{ status: string; record_count?: number }> =>
  (await http.get(`/announcements/${announceNo}/parse-status`, { params: source ? { source } : {} })).data

/** 单行更新（单元格编辑） */
export const updateRecord = async (id: number, data: Partial<AnnouncementRecord>): Promise<{ status: string }> =>
  (await http.patch(`/announcement-record/${id}`, data)).data

/** 批量确认入库 */
export const batchApprove = async (ids: number[]): Promise<{ approved_count: number }> =>
  (await http.post('/announcement-record/batch-approve', { ids })).data

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

export const addFavorite = async (recordId: number): Promise<{ status: string; favorite_id: number }> =>
  (await http.post('/favorites', { record_id: recordId })).data

export const getBatchFavoriteStatus = async (
  recordIds: number[],
): Promise<{ statuses: Record<string, BatchFavoriteStatus | null> }> =>
  (await http.post('/favorites/batch-status', { record_ids: recordIds })).data

export const removeFavorite = async (recordId: number): Promise<{ status: string }> =>
  (await http.delete(`/favorites/${recordId}`)).data

export const listFavorites = async (params?: { status?: string }): Promise<{ favorites: any[] }> =>
  (await http.get('/favorites', { params })).data
