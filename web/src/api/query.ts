// web/src/api/query.ts — 查询与待确认
import http from './http'
import type { QueryResponse, PendingItem } from '../types/api'
import type { RouteTag } from '../types/route-tag'

export const postQuery = async (numbers: string[], forceRefresh: boolean = false, runId?: string): Promise<QueryResponse> =>
  (await http.post('/query', { numbers, run_id: runId }, { params: forceRefresh ? { force_refresh: true } : {} })).data

export const saveQueryResults = async (results: QueryResponse['results']): Promise<{ ok?: boolean }> =>
  (await http.post('/query/save', results)).data

export const getQueryResults = (options?: { routeTag?: RouteTag }) =>
  http.get('/query/results', options)

export const getPendingItems = async (): Promise<{ items: PendingItem[] }> =>
  (await http.get('/pending')).data

export const postRequery = async (numbers: string[], site?: string): Promise<{ results: QueryResponse['results'] }> =>
  (await http.post('/pending/requery', numbers, { params: site ? { site } : {} })).data
