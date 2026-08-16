// web/src/api/notification.ts — 通知配置与日志 API（v2：四渠道全参数）
import http from './http'

export interface WechatChannelConfig {
  enabled: boolean
  webhook_url: string
  corpid?: string
  agentid?: string
  corpsecret?: string
  proxy_url?: string
}

export interface TelegramChannelConfig {
  enabled: boolean
  bot_token: string
  chat_id: string
}

export interface FeishuChannelConfig {
  enabled: boolean
  webhook_url: string
  secret?: string
}

export interface DingTalkChannelConfig {
  enabled: boolean
  webhook_url: string
  secret?: string
}

export type ChannelConfig = WechatChannelConfig | TelegramChannelConfig | FeishuChannelConfig | DingTalkChannelConfig

export interface NotificationConfig {
  enabled: boolean
  channels: {
    wechat: WechatChannelConfig
    telegram: TelegramChannelConfig
    feishu: FeishuChannelConfig
    dingtalk: DingTalkChannelConfig
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
  is_read: boolean
  aggregated_count?: number
  link?: string | null
  icon?: string | null
}

export interface NotificationLogResponse {
  total: number
  page: number
  page_size: number
  items: NotificationLog[]
}

export const getNotificationConfig = (routeTag?: string): Promise<NotificationConfig> =>
  http.get('/notification/config', { routeTag }).then(r => r.data)

export const putNotificationConfig = (data: Partial<NotificationConfig>): Promise<{ ok: boolean }> =>
  http.put('/notification/config', data).then(r => r.data)

export const testNotification = (
  channel: string,
  params?: Record<string, string>,
): Promise<{ ok: boolean; error?: string }> =>
  http.post('/notification/test', { channel, params }).then(r => r.data)

export const getNotificationLogs = (params: {
  page?: number
  page_size?: number
  channel?: string
  status?: string
  start_date?: string
  end_date?: string
  is_read?: boolean
}): Promise<NotificationLogResponse> =>
  http.get('/notification/logs', { params }).then(r => r.data)

export const markNotificationRead = (id?: number | null): Promise<{ ok: boolean; message: string }> =>
  http.post('/notification/read', { id: id ?? null }).then(r => r.data)

export interface NotificationPolicy {
  id: number
  channel: string
  enabled: boolean
  events: string[]
  updated_at: string
}

export const getNotificationPolicies = (): Promise<{ policies: NotificationPolicy[] }> =>
  http.get('/notification/policy').then(r => r.data)

export const putNotificationPolicy = (data: {
  channel: string
  enabled?: boolean
  events?: string[]
}): Promise<{ ok: boolean }> =>
  http.put('/notification/policy', data).then(r => r.data)

/** 清理指定天数前的通知日志（需管理员权限） */
export const deleteNotificationLogs = (days: number = 30): Promise<{ ok: boolean; deleted: number }> =>
  http.delete('/notification/logs', { params: { days } }).then(r => r.data)
