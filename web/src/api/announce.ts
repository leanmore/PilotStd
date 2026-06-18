// web/src/api/announce.ts — 公告抓取与结果读取
import http from './http'
import type { AnnounceResponse, SuccessResponse } from '../types/api'

export const getAnnounceResults = (): Promise<AnnounceResponse> =>
  http.get('/announce/results').then(r => r.data)

export const postAnnounceCheck = (sinceDate?: string): Promise<SuccessResponse> =>
  http.post('/announce/check', null, { params: sinceDate ? { since_date: sinceDate } : {} }).then(r => r.data)
