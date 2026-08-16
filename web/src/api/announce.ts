// web/src/api/announce.ts — 公告抓取与结果读取
import http from './http'
import type { RouteTag } from '../types/route-tag'
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

/** 触发附件解析 */
export const triggerParse = (announceNo: string): Promise<{ status: string }> =>
  http.post(`/announcements/${announceNo}/parse`).then(r => r.data)

/** 获取解析状态 */
export const getParseStatus = (announceNo: string): Promise<{ status: string }> =>
  http.get(`/announcements/${announceNo}/parse-status`).then(r => r.data)

/** 单行更新（单元格编辑） */
export const updateRecord = (id: number, data: Partial<AnnouncementRecord>): Promise<{ status: string }> =>
  http.patch(`/announcement-record/${id}`, data).then(r => r.data)

/** 批量确认入库 */
export const batchApprove = (ids: number[]): Promise<{ approved_count: number }> =>
  http.post('/announcement-record/batch-approve', { ids }).then(r => r.data)

// ── Phase 4a: 收藏 ──────────────────────────────────────

export const addFavorite = (recordId: number): Promise<{ status: string; favorite_id: number }> =>
  http.post('/favorites', { record_id: recordId }, { skipGlobalAuthRedirect: true }).then(r => r.data)

export const getFavoriteStatus = (recordId: number): Promise<{ status: string | null; favorite_id: number | null; local_path?: string; error_message?: string }> =>
  http.get(`/favorites/${recordId}/status`).then(r => r.data)

export const getBatchFavoriteStatus = (recordIds: number[]): Promise<{ statuses: Record<string, { favorite_id: number; status: string } | null> }> =>
  http.post('/favorites/batch-status', { record_ids: recordIds }, { skipGlobalAuthRedirect: true }).then(r => r.data)

export const removeFavorite = (recordId: number): Promise<{ status: string }> =>
  http.delete(`/favorites/${recordId}`, { skipGlobalAuthRedirect: true }).then(r => r.data)

export const listFavorites = (params?: { status?: string }): Promise<{ favorites: any[] }> =>
  http.get('/favorites', { params }).then(r => r.data)
