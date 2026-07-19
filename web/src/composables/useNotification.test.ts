// composables/useNotification.test.ts — 通知管理 composable 单元测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'

// Mock API
vi.mock('@/api/notification', () => ({
  markNotificationRead: vi.fn().mockResolvedValue({ ok: true, message: 'done' }),
}))

import { useNotification } from './useNotification'

/** 在虚拟组件上下文中挂载 composable */
function mountComposable() {
  return mount({
    setup() { return useNotification() },
    render: () => h('div'),
  })
}

describe('useNotification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始状态 messages 为空、unreadCount 为 0', () => {
    const wrapper = mountComposable()
    expect(wrapper.vm.messages).toEqual([])
    expect(wrapper.vm.unreadCount).toBe(0)
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
})
