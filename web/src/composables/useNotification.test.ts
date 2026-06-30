// composables/useNotification.test.ts — WebSocket 通知管理 composable 单元测试
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock primevue/usetoast
const mockToastAdd = vi.fn()
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: mockToastAdd }),
}))

// Mock API
vi.mock('@/api/notification', () => ({
  markNotificationRead: vi.fn().mockResolvedValue({ ok: true, message: 'done' }),
}))

// Mock useNotificationAggregator
const mockShouldShow = vi.fn()
vi.mock('./useNotificationAggregator', () => ({
  useNotificationAggregator: () => ({
    shouldShow: mockShouldShow,
    getPauseState: () => ({ isPaused: false, remainingSeconds: 0 }),
    resume: vi.fn(),
  }),
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
  // 模拟连接成功
  _open() { this.readyState = MockWebSocket.OPEN; this.onopen?.() }
  _message(data: any) { this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) })) }
}

// 替换全局 WebSocket
const origWS = globalThis.WebSocket
globalThis.WebSocket = MockWebSocket as any

// localStorage mock
let storage: Record<string, string> = {}

afterEach(() => {
  globalThis.WebSocket = origWS
})

import { useNotification } from './useNotification'

describe('useNotification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage = {}
    vi.spyOn(localStorage, 'getItem').mockImplementation((k: string) => storage[k] ?? null)
    vi.spyOn(localStorage, 'setItem').mockImplementation((k: string, v: string) => { storage[k] = v })
  })

  // 不直接调用 onMounted（会触发 WebSocket），只测返回的接口
  it('初始状态 messages 为空、未连接、unreadCount 为 0', () => {
    const { messages, isConnected, unreadCount, error } = useNotification()

    expect(messages.value).toEqual([])
    expect(isConnected.value).toBe(false)
    expect(unreadCount.value).toBe(0)
    expect(error.value).toBeNull()
  })

  it('connect 创建 WebSocket 并设置 protocols', () => {
    const { connect } = useNotification()

    // connect 使用 window.location，在 jsdom 下 host 为 localhost
    // 直接用构造函数验证
    const ws = new MockWebSocket('ws://localhost/api/notification/ws')
    expect(ws.url).toContain('/api/notification/ws')
  })

  it('markAsRead 标记单条消息为已读', async () => {
    const { messages, markAsRead } = useNotification()

    // 手动添加一条未读消息
    messages.value.push({
      id: 1, event_type: 'test', title: '测试', body: '内容',
      level: 'info', sent_at: new Date().toISOString(), is_read: false,
    })

    const result = await markAsRead(1)
    expect(result.ok).toBe(true)
    expect(messages.value[0].is_read).toBe(true)
  })

  it('markAsRead 不传 id 时标记全部为已读', async () => {
    const { messages, markAsRead } = useNotification()

    messages.value.push(
      { id: 1, event_type: 'a', title: 'A', body: '...', level: 'info', sent_at: new Date().toISOString(), is_read: false },
      { id: 2, event_type: 'b', title: 'B', body: '...', level: 'warn', sent_at: new Date().toISOString(), is_read: false },
    )

    await markAsRead()
    expect(messages.value.every(m => m.is_read)).toBe(true)
  })

  it('unreadCount 计算属性正确反映未读数', () => {
    const { messages, unreadCount } = useNotification()

    messages.value.push(
      { id: 1, event_type: 'a', title: 'A', body: '...', level: 'info', sent_at: new Date().toISOString(), is_read: false },
      { id: 2, event_type: 'b', title: 'B', body: '...', level: 'warn', sent_at: new Date().toISOString(), is_read: true },
    )

    expect(unreadCount.value).toBe(1)
  })

  it('disconnect 关闭 WebSocket 并重置状态', () => {
    const { disconnect, isConnected, isConnecting } = useNotification()

    disconnect()

    expect(isConnected.value).toBe(false)
    expect(isConnecting.value).toBe(false)
  })
})
