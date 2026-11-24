// api/notification.test.ts — 通知配置 / 渠道元数据 / 日志 / 策略 API（NEW-44）
//
// 只测本模块自己的契约：路径、query/body 分工、可选字段的缺省形状（尤其
// `event_classes: []` 表示“清空该层”，不能被 falsy 判断丢掉）、返回值取 .data。
// 已有 `__tests__/notification.test.ts` 覆盖旧五函数；本文件覆盖新增端点与易回归字段。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }))
vi.mock('./http', () => ({ default: h }))

import {
  deleteNotificationLogs, getNotificationChannels, getNotificationConfig,
  getNotificationFailedItems, getNotificationLogs, getNotificationPolicies,
  getNotificationSpec, markNotificationRead, putNotificationConfig,
  putNotificationPolicy, putQuietHours, testNotification,
} from './notification'

describe('notification API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getNotificationConfig 走 GET /notification/config 并透传 routeTag', async () => {
    const config = { enabled: true, channels: {}, rules: {} }
    h.get.mockResolvedValueOnce({ data: config })

    await expect(getNotificationConfig('/settings')).resolves.toEqual(config)
    expect(h.get).toHaveBeenCalledWith('/notification/config', { routeTag: '/settings' })
  })

  it('渠道/事件元数据分别走 channels 与 spec（返回后端声明顺序与哈希）', async () => {
    const channels = { spec_hash: 'abc', channels: [], notify_events: ['a'], event_class_map: {} }
    h.get.mockResolvedValue({ data: channels })

    await expect(getNotificationChannels('/settings')).resolves.toEqual(channels)
    expect(h.get).toHaveBeenLastCalledWith('/notification/channels', { routeTag: '/settings' })

    h.get.mockResolvedValueOnce({ data: { events: ['download.completed'] } })
    await expect(getNotificationSpec()).resolves.toEqual({ events: ['download.completed'] })
    expect(h.get).toHaveBeenLastCalledWith('/notification/spec', { routeTag: undefined })
  })

  it('putNotificationConfig / putQuietHours 直接以入参为 PUT body（增量语义）', async () => {
    h.put.mockResolvedValue({ data: { ok: true } })

    await putNotificationConfig({ channels: { telegram: { enabled: false } } })
    expect(h.put).toHaveBeenLastCalledWith('/notification/config', {
      channels: { telegram: { enabled: false } },
    })

    await putQuietHours({ enabled: true, start: '22:00', end: '08:00' })
    expect(h.put).toHaveBeenLastCalledWith('/notification/quiet-hours', {
      enabled: true,
      start: '22:00',
      end: '08:00',
    })
  })

  it('testNotification 提交 channel 与渠道参数（params 缺省为 undefined）', async () => {
    h.post.mockResolvedValue({ data: { ok: true } })

    await testNotification('telegram', { bot_token: 'tk', chat_id: '1' })
    expect(h.post).toHaveBeenLastCalledWith('/notification/test', {
      channel: 'telegram',
      params: { bot_token: 'tk', chat_id: '1' },
    })

    await testNotification('wechat')
    expect(h.post).toHaveBeenLastCalledWith('/notification/test', {
      channel: 'wechat',
      params: undefined,
    })
  })

  it('getNotificationLogs 透传完整筛选 params 与 routeTag（is_read=false 不能丢）', async () => {
    const payload = { total: 0, page: 1, page_size: 20, items: [] }
    h.get.mockResolvedValueOnce({ data: payload })
    const params = { page: 2, page_size: 50, channel: 'wechat', status: 'failed', is_read: false }

    await expect(getNotificationLogs(params, '/notification-logs')).resolves.toEqual(payload)
    expect(h.get).toHaveBeenCalledWith('/notification/logs', {
      params,
      routeTag: '/notification-logs',
    })
  })

  it('getNotificationFailedItems 按 logId 插值路径，分页默认 1/20', async () => {
    const payload = { total: 0, page: 1, page_size: 20, items: [] }
    h.get.mockResolvedValueOnce({ data: payload })

    await expect(getNotificationFailedItems(88)).resolves.toEqual(payload)
    expect(h.get).toHaveBeenCalledWith('/notification/logs/88/failed-items', {
      params: { page: 1, page_size: 20 },
    })
  })

  it('markNotificationRead：单条传 id，null/undefined 归一为 null（标记全部）', async () => {
    h.post.mockResolvedValue({ data: { ok: true, message: 'done' } })

    await markNotificationRead(42)
    expect(h.post).toHaveBeenLastCalledWith('/notification/read', { id: 42 })

    await markNotificationRead(null)
    expect(h.post).toHaveBeenLastCalledWith('/notification/read', { id: null })

    await markNotificationRead()
    expect(h.post).toHaveBeenLastCalledWith('/notification/read', { id: null })
  })

  it('deleteNotificationLogs 默认清理 30 天前，天数放 query', async () => {
    h.delete.mockResolvedValue({ data: { ok: true, deleted: 0 } })

    await deleteNotificationLogs()
    expect(h.delete).toHaveBeenLastCalledWith('/notification/logs', { params: { days: 30 } })

    await deleteNotificationLogs(7)
    expect(h.delete).toHaveBeenLastCalledWith('/notification/logs', { params: { days: 7 } })
  })

  it('getNotificationPolicies / putNotificationPolicy：event_classes: [] 表示清空该层', async () => {
    const policies = { policies: [] }
    h.get.mockResolvedValueOnce({ data: policies })
    await expect(getNotificationPolicies()).resolves.toEqual(policies)
    expect(h.get).toHaveBeenCalledWith('/notification/policy')

    h.put.mockResolvedValue({ data: { ok: true } })
    await putNotificationPolicy({ channel: 'wechat', event_classes: [] })
    // 空数组是“清空类别层”的合法语义，不能被 falsy 判断丢掉
    expect(h.put).toHaveBeenCalledWith('/notification/policy', {
      channel: 'wechat',
      event_classes: [],
    })
  })

  it('失败原样透传（不吞错）', async () => {
    const err = new Error('notification 500')
    h.get.mockRejectedValueOnce(err)

    await expect(getNotificationPolicies()).rejects.toBe(err)
  })
})
