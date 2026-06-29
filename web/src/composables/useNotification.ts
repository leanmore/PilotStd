// web/src/composables/useNotification.ts
// WebSocket 连接管理 + 通知状态管理 + 自动重连
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { markNotificationRead, type NotificationLog } from '@/api/notification'

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
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const error = ref<string | null>(null)
  const messages = ref<NotificationMessage[]>([])
  const toast = useToast()

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  const MAX_RECONNECT_ATTEMPTS = 10

  const connect = () => {
    if (isConnecting.value || (ws.value?.readyState === WebSocket.OPEN)) {
      return
    }

    isConnecting.value = true
    error.value = null

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/notification/ws`

    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      isConnected.value = true
      isConnecting.value = false
      error.value = null
      reconnectAttempts = 0
    }

    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.unshift({ ...data, is_read: false })

        const toastConfig = getToastConfig()
        if (toastConfig.enabled && toastConfig.events.includes(data.event_type)) {
          const severityMap: Record<string, 'info' | 'warn' | 'error' | 'success'> = {
            info: 'info',
            warning: 'warn',
            error: 'error',
          }
          toast.add({
            severity: severityMap[data.level] || 'info',
            summary: data.title,
            detail: data.body,
            life: 5000,
            closable: true,
          })
        }
      } catch (e) {
        console.error('解析通知消息失败:', e)
      }
    }

    ws.value.onclose = () => {
      isConnected.value = false
      isConnecting.value = false
      scheduleReconnect()
    }

    ws.value.onerror = () => {
      error.value = 'WebSocket 连接失败'
      isConnecting.value = false
    }
  }

  const scheduleReconnect = () => {
    if (reconnectTimer) return
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      error.value = 'WebSocket 连接失败，请刷新页面重试'
      return
    }
    reconnectAttempts++
    error.value = `WebSocket 连接断开，5秒后重试...`
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, 5000)
  }

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    isConnected.value = false
    isConnecting.value = false
  }

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

  const getToastConfig = () => {
    const saved = localStorage.getItem('notification_toast_config')
    if (saved) {
      try {
        return JSON.parse(saved)
      } catch {
        /* ignore */
      }
    }
    return {
      enabled: true,
      events: ['auto_scan_failed', 'validity_system_failed', 'validity_standard_failed'],
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    messages,
    unreadCount: computed(() => messages.value.filter((m) => !m.is_read).length),
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    markAsRead,
    reconnectAttempts,
  }
}
