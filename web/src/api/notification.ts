// web/src/api/notification.ts — 通知配置与日志 API
import http from './http'

export interface NotificationConfig {
  enabled: boolean
  channels: {
    wechat: { webhook_url: string; enabled: boolean; events: string[] }
    telegram: { bot_token: string; chat_id: string; enabled: boolean; events: string[] }
    feishu: { webhook_url: string; enabled: boolean; events: string[] }
  }
  rules: Record<string, string[]>
}

export interface NotificationLog {
  id: number
  event_type: string
  channel: string
  title: string
  body: string
  standard_number: string | null
  status: string
  error_msg: string | null
  sent_at: string
}

export interface NotificationLogResponse {
  total: number
  page: number
  page_size: number
  items: NotificationLog[]
}

export const getNotificationConfig = (): Promise<NotificationConfig> =>
  http.get('/notification/config').then(r => r.data)

export const putNotificationConfig = (data: Partial<NotificationConfig>): Promise<{ ok: boolean }> =>
  http.put('/notification/config', data).then(r => r.data)

export const testNotification = (channel: string): Promise<{ ok: boolean; error?: string }> =>
  http.post('/notification/test', { channel }).then(r => r.data)

export const getNotificationLogs = (params: {
  page?: number
  page_size?: number
  channel?: string
  status?: string
  start_date?: string
  end_date?: string
}): Promise<NotificationLogResponse> =>
  http.get('/notification/logs', { params }).then(r => r.data)
