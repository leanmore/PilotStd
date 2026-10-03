// web/src/api/notification.ts — 通知配置与日志 API（v2：四渠道全参数）
import http from './http'
import type { RouteTag } from '../types/route-tag'

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

/**
 * 保存/更新配置的请求体：渠道内字段允许部分提交（敏感字段掩码/空值不提交，
 * 由后端保留 DB 原值——增量语义，见 NotificationConfig.vue cleanChannel）。
 */
export interface NotificationConfigUpdate {
  enabled?: boolean
  channels?: {
    wechat?: Partial<WechatChannelConfig>
    telegram?: Partial<TelegramChannelConfig>
    feishu?: Partial<FeishuChannelConfig>
    dingtalk?: Partial<DingTalkChannelConfig>
  }
  rules?: Record<string, string[]>
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
  // 说明（已核实）：后端 `GET /api/notification/logs` **不返回**下面三个字段
  // （docker/api/notification.py 显式构造 10 个字段，不含它们），故前端不得据此渲染。
  // 声明保留仅为记录曾存在的契约；若后端将来补上，需同步确认前端消费方。
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

export const getNotificationConfig = (routeTag?: RouteTag): Promise<NotificationConfig> =>
  http.get('/notification/config', { routeTag }).then(r => r.data)

// ── 渠道元数据（步 A C2 新增）：`GET /api/notification/channels` ──
// 渠道的**唯一事实来源**是后端 `channel_spec.py`；前端不再硬编码渠道清单与字段。
// 只含渲染所需的元数据，**不含**凭证值（凭证视图仍由 `getNotificationConfig` 提供）。
export interface ChannelFieldSpec {
  name: string
  /** 控件形态：`string`（InputText）/ `password`（Password）/ `text_password`（InputText type=password） */
  type: 'string' | 'password' | 'text_password'
  /** 前端 locales 键（优先）；为空则回退 `label` 字面量 */
  label_key: string
  label: string
  required: boolean
  /** 是否在 API 响应中掩码，且提交时是否跳过掩码回显值 */
  mask: boolean
  /** 输入控件是否用密码形态（`type` 的粗粒度视图） */
  password: boolean
  placeholder: string
  placeholder_key: string
  badge_key: string
  divider_key: string
}

export interface ChannelStatusBranch {
  all_of: string[]
  label_key: string
}

/** "已配置"判定规则：按序匹配分支，全不命中则用兜底文案键 */
export interface ChannelStatusRule {
  branches: ChannelStatusBranch[]
  fallback_key: string
}

export interface ChannelSpec {
  name: string
  label_key: string
  icon: string
  enabled_default: boolean
  hint_key: string
  fields: ChannelFieldSpec[]
  status_rule: ChannelStatusRule
}

export interface NotificationChannelsResponse {
  /** 负载本体的规范化 JSON 哈希（前 16 位）：变化即需重建表单（内容级缓存失效） */
  spec_hash: string
  channels: ChannelSpec[]
}

export const getNotificationChannels = (routeTag?: RouteTag): Promise<NotificationChannelsResponse> =>
  http.get('/notification/channels', { routeTag }).then(r => r.data)

export const putNotificationConfig = (data: NotificationConfigUpdate): Promise<{ ok: boolean }> =>
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
}, routeTag?: RouteTag): Promise<NotificationLogResponse> =>
  http.get('/notification/logs', { params, routeTag }).then(r => r.data)

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
