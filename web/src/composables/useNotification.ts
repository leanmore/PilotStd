// web/src/composables/useNotification.ts
// 通知状态管理——30s 轮询 + 可见性感知（阶段 0，2026-10-02 通知架构重设计）
//
// 历史：原实现是"HTTP 轮询模式"的注释 + 恒空 `ref([])`——messages 从未被填充，
// 铃铛角标恒 0、下拉恒空（装饰性组件）。本文件把注释里的承诺兑现：
// 轮询 `GET /api/notification/logs`，并在页面隐藏时停轮询（NAS 上常驻的浏览器尤其实惠）。
//
// 设计约束（详见 docs/plans/notification-redesign/06-阶段0-1实施方案.md §1.1）：
// - 单例状态 + 引用计数：多个使用方共享同一份数据与同一个定时器（否则 N 个组件 = N 倍请求）。
// - 失败不清空数据：清空会让角标"闪没"，比不刷新更差。
// - 连续失败达上限后停轮询：避免后端挂掉时无谓刷请求（等待手动 refresh 或重新挂载）。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getNotificationLogs, markNotificationRead } from '@/api/notification'

/** 轮询间隔（毫秒）。改此常量即可调速；单用户自建服务、通知非紧急，30s 足够。 */
export const POLL_INTERVAL_MS = 30_000

/** 连续失败上限：达到即停轮询（单次失败静默重试）。 */
const MAX_CONSECUTIVE_FAILURES = 3

export interface NotificationMessage {
  id?: number
  event_type: string
  title: string
  body: string
  /**
   * 后端 `GET /api/notification/logs` **不返回** level 字段（该端点显式只构造 10 个字段），
   * 故映射层统一填 'info'。取值域与后端 `NotificationMessage.level` 对齐（info/warning/error）——
   * 原声明写的是 'warn'，与后端 'warning' 不符，本次一并纠正。
   */
  level: 'info' | 'warning' | 'error'
  sent_at: string
  is_read?: boolean
}

/** 后端日志项的字段子集（对应 docker/api/notification.py:368-382 的 10 字段响应）。 */
interface NotificationLogItem {
  id: number
  event_type: string
  title: string | null
  body: string | null
  sent_at: string
  is_read: number | boolean
}

// ── 模块级单例状态（多个使用方共享）────────────────────────────────────────────
const messages = ref<NotificationMessage[]>([])
const error = ref('')
const loading = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
let subscribers = 0
let consecutiveFailures = 0
let visibilityBound = false

/**
 * 后端日志项 → 前端消息。
 *
 * 两处必须显式映射（否则角标算错 / 类型不符）：
 * 1. `is_read` 后端是 0/1 数字，前端按布尔使用 → `Boolean()`
 * 2. 后端不返回 `level` → 填 'info'（见 interface 注释）
 */
function normalize(item: NotificationLogItem): NotificationMessage {
  return {
    id: item.id,
    event_type: item.event_type,
    title: item.title ?? '',
    body: item.body ?? '',
    level: 'info',
    sent_at: item.sent_at,
    is_read: Boolean(item.is_read),
  }
}

function stopPolling(): void {
  if (timer === null) return
  clearInterval(timer)
  timer = null
}

function startPolling(): void {
  if (timer !== null) return
  timer = setInterval(() => {
    // 轮询期间切到后台标签页：本轮直接跳过（不发起请求）
    if (typeof document !== 'undefined' && document.hidden) return
    void refresh()
  }, POLL_INTERVAL_MS)
}

/**
 * 拉取最近通知（当前页）。
 *
 * 失败语义：`error` 记录最近一次失败原因、数据保持原样；
 * 连续失败达 `MAX_CONSECUTIVE_FAILURES` 时停止轮询（`error` 里带提示）。
 */
async function refresh(): Promise<void> {
  loading.value = true
  try {
    const res = await getNotificationLogs({ page: 1, page_size: 20 }, '/notification-logs')
    const items = (res?.items ?? []) as NotificationLogItem[]
    messages.value = items.map(normalize)
    error.value = ''
    consecutiveFailures = 0
  } catch (e) {
    consecutiveFailures += 1
    error.value = String(e)
    // 开发者可见的告警（与 markAsRead 的 console.error 同口径）；不打扰用户界面
    console.warn('通知列表获取失败:', e) // i18n-allow: 开发者日志：通知列表获取失败
    if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
      stopPolling()
      console.warn(`通知轮询已停止：连续 ${consecutiveFailures} 次失败`) // i18n-allow: 开发者日志：轮询停止
    }
  } finally {
    loading.value = false
  }
}

/** 可见性变化：隐藏 → 停；恢复可见 → 立即拉一次并重启（不等下一个间隔）。 */
function onVisibilityChange(): void {
  if (document.hidden) {
    stopPolling()
    return
  }
  void refresh()
  startPolling()
}

function bindVisibility(): void {
  if (visibilityBound || typeof document === 'undefined') return
  document.addEventListener('visibilitychange', onVisibilityChange)
  visibilityBound = true
}

function unbindVisibility(): void {
  if (!visibilityBound || typeof document === 'undefined') return
  document.removeEventListener('visibilitychange', onVisibilityChange)
  visibilityBound = false
}

export function useNotification() {
  const markAsRead = async (id?: number) => {
    try {
      const result = await markNotificationRead(id)
      if (result.ok) {
        if (id) {
          const msg = messages.value.find((m) => m.id === id)
          if (msg) msg.is_read = true
        } else {
          // 后端把全表标为已读；本地同步整份列表，避免下轮轮询前角标残留
          for (const m of messages.value) m.is_read = true
        }
      }
      return result
    } catch (e) {
      console.error('标记已读失败:', e) // i18n-allow: 开发者日志：标记已读失败
      return { ok: false, error: String(e) }
    }
  }

  onMounted(() => {
    subscribers += 1
    bindVisibility()
    void refresh()
    // 挂载时若页面已在后台，则不起定时器（恢复可见时再起）
    if (typeof document === 'undefined' || !document.hidden) startPolling()
  })

  onUnmounted(() => {
    subscribers -= 1
    if (subscribers <= 0) {
      subscribers = 0
      stopPolling()
      unbindVisibility()
    }
  })

  return {
    messages,
    error,
    loading,
    unreadCount: computed(() => messages.value.filter((m) => !m.is_read).length),
    markAsRead,
    refresh,
  }
}
