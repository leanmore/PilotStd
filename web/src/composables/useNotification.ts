// web/src/composables/useNotification.ts
// 通知状态管理（HTTP 轮询模式，WebSocket 端点已删除）
import { ref, computed } from 'vue'
import { markNotificationRead } from '@/api/notification'

export interface NotificationMessage {
  id?: number
  event_type: string
  title: string
  body: string
  level: 'info' | 'warn' | 'error'
  sent_at: string
  is_read?: boolean
}

export function useNotification() {
  const messages = ref<NotificationMessage[]>([])

  const markAsRead = async (id?: number) => {
    try {
      const result = await markNotificationRead(id)
      if (result.ok) {
        if (id) {
          const msg = messages.value.find((m) => m.id === id)
          if (msg) msg.is_read = true
        } else {
          for (const m of messages.value) m.is_read = true
        }
      }
      return result
    } catch (e) {
      console.error('标记已读失败:', e)
      return { ok: false, error: String(e) }
    }
  }

  return {
    messages,
    unreadCount: computed(() => messages.value.filter((m) => !m.is_read).length),
    markAsRead,
  }
}
