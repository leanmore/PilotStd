// composables/useNotification.test.ts — WebSocket 通知管理 composable 单元测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'

// Mock API
vi.mock('@/api/notification', () => ({
  markNotificationRead: vi.fn().mockResolvedValue({ ok: true, message: 'done' }),
}))

// 模拟 WebSocket
class MockWebSocket {
  url: string
  readyState: number
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  static OPEN = 1
  static CLOSED = 3

  constructor(url: string) {
    this.url = url
    this.readyState = MockWebSocket.CLOSED
  }

  close() { this.readyState = MockWebSocket.CLOSED; this.onclose?.() }
  _open() { this.readyState = MockWebSocket.OPEN; this.onopen?.() }
  _message(data: any) { this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) })) }
}

const origWS = globalThis.WebSocket
globalThis.WebSocket = MockWebSocket as any

let storage: Record<string, string> = {}

import { useNotification } from './useNotification'

/** 在虚拟组件上下文中挂载 composable，消除 onMounted 警告 */
function mountComposable() {
  return mount({
    setup() { return useNotification() },
    render: () => h('div'),
  })
}

describe('useNotification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage = {}
    vi.spyOn(localStorage, 'getItem').mockImplementation((k: string) => storage[k] ?? null)
    vi.spyOn(localStorage, 'setItem').mockImplementation((k: string, v: string) => { storage[k] = v })
  })

  afterEach(() => {
    globalThis.WebSocket = origWS
  })

  it('初始状态 messages 为空、未连接、unreadCount 为 0', () => {
    const wrapper = mountComposable()
    expect(wrapper.vm.messages).toEqual([])
    expect(wrapper.vm.isConnected).toBe(false)
    expect(wrapper.vm.unreadCount).toBe(0)
    expect(wrapper.vm.error).toBeNull()
  })

  it('connect 不重复创建已打开的 WebSocket', () => {
    const wrapper = mountComposable()
    wrapper.vm.connect()
    expect(wrapper.vm.isConnecting).toBe(true)
    // 再次 connect 不应创建新连接
    const wsBefore = (wrapper.vm as any).ws
    wrapper.vm.connect()
    expect(wrapper.vm.isConnecting).toBe(true)
  })

  it('markAsRead 标记单条消息为已读', async () => {
    const wrapper = mountComposable()
    wrapper.vm.messages.push({
      id: 1, event_type: 'test', title: '测试', body: '内容',
      level: 'info', sent_at: new Date().toISOString(), is_read: false,
    })
    const result = await wrapper.vm.markAsRead(1)
    expect(result.ok).toBe(true)
    expect(wrapper.vm.messages[0].is_read).toBe(true)
  })

  it('markAsRead 不传 id 时标记全部为已读', async () => {
    const wrapper = mountComposable()
    wrapper.vm.messages.push(
      { id: 1, event_type: 'a', title: 'A', body: '...', level: 'info', sent_at: new Date().toISOString(), is_read: false },
      { id: 2, event_type: 'b', title: 'B', body: '...', level: 'warn', sent_at: new Date().toISOString(), is_read: false },
    )
    await wrapper.vm.markAsRead()
    expect(wrapper.vm.messages.every((m: { is_read: boolean }) => m.is_read)).toBe(true)
  })

  it('unreadCount 计算属性正确反映未读数', () => {
    const wrapper = mountComposable()
    wrapper.vm.messages.push(
      { id: 1, event_type: 'a', title: 'A', body: '...', level: 'info', sent_at: new Date().toISOString(), is_read: false },
      { id: 2, event_type: 'b', title: 'B', body: '...', level: 'warn', sent_at: new Date().toISOString(), is_read: true },
    )
    expect(wrapper.vm.unreadCount).toBe(1)
  })

  it('disconnect 关闭 WebSocket 并重置状态', () => {
    const wrapper = mountComposable()
    wrapper.vm.disconnect()
    expect(wrapper.vm.isConnected).toBe(false)
    expect(wrapper.vm.isConnecting).toBe(false)
  })
})
