// web/src/api/apiKeys.ts — API Key 管理
import http from './http'

export interface ApiKey {
  id: number
  key_id: string
  description: string
  scopes: string[]
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  is_active: number
  created_by: string
}

export const getApiKeys = (): Promise<{ api_keys: ApiKey[] }> =>
  http.get('/admin/api-keys').then(r => r.data)

export const createApiKey = (data: {
  key_id: string
  description: string
  scopes: string[]
  expires_at: string
}): Promise<{ ok: boolean; key_id: string; raw_key: string }> =>
  http.post('/admin/api-keys', data).then(r => r.data)

export const updateApiKey = (
  keyId: string,
  data: { description?: string; scopes?: string[]; expires_at?: string }
): Promise<{ ok: boolean }> =>
  http.put(`/admin/api-keys/${keyId}`, data).then(r => r.data)

export const revokeApiKey = (keyId: string): Promise<{ ok: boolean }> =>
  http.delete(`/admin/api-keys/${keyId}`).then(r => r.data)

export const reactivateApiKey = (keyId: string): Promise<{ ok: boolean }> =>
  http.put(`/admin/api-keys/${keyId}/reactivate`).then(r => r.data)
