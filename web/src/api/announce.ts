// web/src/api/announce.ts — 公告抓取与结果读取
import http from './http'
import type { AnnounceResponse, SuccessResponse } from '../types/api'

export const getAnnounceResults = (sourceSite?: string): Promise<AnnounceResponse> =>
  http.get('/announce/results', { params: sourceSite ? { source_site: sourceSite } : {} }).then(r => r.data)

export const postAnnounceCheck = (sinceDate?: string): Promise<SuccessResponse> =>
  http.post('/announce/check', null, { params: sinceDate ? { since_date: sinceDate } : {} }).then(r => r.data)
