// web/src/api/query.ts — 查询与待确认
import http from './http'
import type { QueryResponse, PendingItem } from '../types/api'

export const postQuery = (numbers: string[], forceRefresh: boolean = false, runId?: string): Promise<QueryResponse> =>
  http.post('/query', { numbers, run_id: runId }, { params: forceRefresh ? { force_refresh: true } : {} }).then(r => r.data)

export const saveQueryResults = (results: QueryResponse['results']): Promise<{ ok?: boolean }> =>
  http.post('/query/save', results).then(r => r.data)

export const getQueryResults = (): Promise<QueryResponse['results']> =>
  http.get('/query/results').then(r => r.data)

export const getPendingItems = (): Promise<{ items: PendingItem[] }> =>
  http.get('/pending').then(r => r.data)

export const postRequery = (numbers: string[], site?: string): Promise<{ results: QueryResponse['results'] }> =>
  http.post('/pending/requery', numbers, { params: site ? { site } : {} }).then(r => r.data)
