// composables/useNotification.test.ts — 通知 composable 单元测试
// 阶段 0（2026-10-02）：原实现 messages 恒空、从不请求；现改为 30s 轮询 + 可见性感知。
// 本文件的用例对**旧实现**必须 FAIL（见每条 ★ 说明）。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

// 后端返回形状（docker/api/notification.py:368-382 的 10 字段子集）；
// is_read 是 **0/1 数字**，level 字段后端不返回——两者是映射层的核心断言点。
const LOG_ITEMS = [
  {
    id: 1,
    event_type: 'archive_complete',
    channel: 'wechat',
    title: '归档完成',
    body: '已归档 3 个文件',
    standard_number: null,
    status: 'success',
    error_msg: null,
    sent_at: '2026-10-02T10:00:00',
    is_read: 0,
  },
  {
    id: 2,
    event_type: 'auto_scan_failed',
    channel: 'wechat',
    title: '扫描异常',
    body: '连接超时',
    standard_number: null,
    status: 'failed',
    error_msg: 'timeout',
    sent_at: '2026-10-02T09:00:00',
    is_read: 1,
  },
]

const mocks = vi.hoisted(() => ({
  markNotificationRead: vi.fn(),
  getNotificationLogs: vi.fn(),
}))

vi.mock('@/api/notification', () => ({
  markNotificationRead: mocks.markNotificationRead,
  getNotificationLogs: mocks.getNotificationLogs,
}))

import { useNotification, POLL_INTERVAL_MS } from './useNotification'

/** 在虚拟组件上下文中挂载 composable（onMounted/onUnmounted 才会执行）。 */
function mountComposable() {
  return mount(
    defineComponent({
      setup() {
        return useNotification()
      },
      render: () => h('div'),
    }),
  )
}

/** 等一轮微任务（refresh 内部 await 的 resolve 落地）。 */
const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('useNotification', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mocks.getNotificationLogs.mockReset().mockResolvedValue({ total: 2, page: 1, page_size: 20, items: LOG_ITEMS })
    mocks.markNotificationRead.mockReset().mockResolvedValue({ ok: true, count: 1, message: 'done' })
    setHidden(false)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('挂载后立即拉取一次通知列表（旧实现从不请求 → 本用例 FAIL）', async () => {
    const w = mountComposable()
    await flush()
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1)
    expect(mocks.getNotificationLogs).toHaveBeenCalledWith({ page: 1, page_size: 20 }, '/notification-logs')
    expect(w.vm.messages).toHaveLength(2)
    w.unmount()
  })

  it('角标 unreadCount 反映真实未读数（is_read 0/1 → 布尔）', async () => {
    const w = mountComposable()
    await flush()
    // 造第 3 条未读，确认计数随数据变化
    mocks.getNotificationLogs.mockResolvedValue({
      items: [...LOG_ITEMS, { ...LOG_ITEMS[0], id: 3, is_read: 0 }],
    })
    await w.vm.refresh()
    expect(w.vm.unreadCount).toBe(2)
    expect(w.vm.messages[0].is_read).toBe(false) // 0 → false（★ 类型映射）
    expect(w.vm.messages[1].is_read).toBe(true) // 1 → true
    w.unmount()
  })

  it('level 后端不返回时填 info（防后人误以为后端会返回）', async () => {
    const w = mountComposable()
    await flush()
    expect(w.vm.messages.every((m: { level: string }) => m.level === 'info')).toBe(true)
    // 后端响应体确实没有 level 字段——这条断言锁住"缺省来自映射层"这一事实
    expect(Object.prototype.hasOwnProperty.call(LOG_ITEMS[0], 'level')).toBe(false)
    w.unmount()
  })

  it('title/body 为 null 时回落空串（列可空）', async () => {
    mocks.getNotificationLogs.mockResolvedValue({
      items: [{ ...LOG_ITEMS[0], title: null, body: null }],
    })
    const w = mountComposable()
    await flush()
    expect(w.vm.messages[0].title).toBe('')
    expect(w.vm.messages[0].body).toBe('')
    w.unmount()
  })

  it('30 秒轮询一次（间隔等于 POLL_INTERVAL_MS）', async () => {
    const w = mountComposable()
    await flush()
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS - 1)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1) // 未到点不请求

    await vi.advanceTimersByTimeAsync(1)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(2) // 到点请求一次

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(3)
    w.unmount()
  })

  it('页面隐藏时暂停轮询（推进 3 个间隔，请求数不增）', async () => {
    const w = mountComposable()
    await flush()
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1)

    setHidden(true)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1) // ★ 隐藏期间零请求
    w.unmount()
  })

  it('恢复可见时立即拉一次并重启轮询（不等间隔）', async () => {
    const w = mountComposable()
    await flush()
    setHidden(true)
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1)

    setHidden(false)
    await flush()
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(2) // ★ 立即请求

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(3) // 且轮询已重启
    w.unmount()
  })

  it('单次失败不清空已有数据（保留上次结果 + 记录 error）', async () => {
    const w = mountComposable()
    await flush()
    expect(w.vm.messages).toHaveLength(2)

    mocks.getNotificationLogs.mockRejectedValueOnce(new Error('network down'))
    await w.vm.refresh()
    expect(w.vm.messages).toHaveLength(2) // ★ 不清空
    expect(String(w.vm.error)).toContain('network down')
    w.unmount()
  })

  it('连续 3 次失败后停止轮询', async () => {
    const w = mountComposable()
    await flush()
    mocks.getNotificationLogs.mockRejectedValue(new Error('boom'))

    await w.vm.refresh()
    await w.vm.refresh()
    await w.vm.refresh()
    const callsAfterFailures = mocks.getNotificationLogs.mock.calls.length

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
    expect(mocks.getNotificationLogs.mock.calls.length).toBe(callsAfterFailures) // ★ 已停
    w.unmount()
  })

  it('多个使用方共享同一份数据与同一个定时器（不产生 N 倍请求）', async () => {
    const a = mountComposable()
    const b = mountComposable()
    await flush()
    // 两个使用方各自 refresh 一次（挂载各一次），但没有 N 倍定时器
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(2)

    mocks.getNotificationLogs.mockClear()
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1) // ★ 单一定时器
    expect(a.vm.messages).toBe(b.vm.messages) // 共享同一 ref（单例状态）

    // 卸载一个不应停掉另一个的轮询
    a.unmount()
    mocks.getNotificationLogs.mockClear()
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(1)

    b.unmount()
    mocks.getNotificationLogs.mockClear()
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    expect(mocks.getNotificationLogs).toHaveBeenCalledTimes(0) // ★ 最后一个卸载后才停
  })

  it('markAsRead 标记单条消息为已读', async () => {
    const w = mountComposable()
    await flush()
    const result = await w.vm.markAsRead(1)
    expect(result.ok).toBe(true)
    expect(mocks.markNotificationRead).toHaveBeenCalledWith(1)
    expect(w.vm.messages[0].is_read).toBe(true)
    w.unmount()
  })

  it('markAsRead 不传 id 时把整份本地列表标记为已读（角标不残留）', async () => {
    const w = mountComposable()
    await flush()
    await w.vm.markAsRead()
    expect(mocks.markNotificationRead).toHaveBeenCalledWith(undefined)
    expect(w.vm.messages.every((m: { is_read?: boolean }) => m.is_read)).toBe(true)
    expect(w.vm.unreadCount).toBe(0)
    w.unmount()
  })
})
