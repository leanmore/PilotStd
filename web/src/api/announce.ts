// web/src/api/announce.ts — 公告抓取与结果读取
import http from './http'
import type {
  AnnounceResponse,
  SuccessResponse,
  AnnouncementDetail,
  AnnouncementRecord,
} from '../types/api'

export const getAnnounceResults = (sourceSite?: string, fromDate?: string): Promise<AnnounceResponse> =>
  http.get('/announce/results', { params: { source_site: sourceSite || '', from_date: fromDate || '' } }).then(r => r.data)

export const postAnnounceCheck = (sinceDate?: string, types?: string): Promise<SuccessResponse> =>
  http.post('/announce/check', null, { params: { ...(sinceDate ? { since_date: sinceDate } : {}), ...(types ? { types } : {}) } }).then(r => r.data)

// ── Phase 3: 公告详情 ──────────────────────────────────

/** 获取公告详情 */
export const getAnnouncementDetail = (announceNo: string): Promise<AnnouncementDetail> =>
  http.get(`/announcements/${announceNo}`).then(r => r.data)

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
