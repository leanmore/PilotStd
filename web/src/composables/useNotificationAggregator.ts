// web/src/composables/useNotificationAggregator.ts
// 通知智能聚合器 — 缓冲合并 + 熔断暂停（与 WinUI 端行为等价）
import { ref, computed } from 'vue'

interface BufferItem {
  level: string
  title: string
  body: string
  timestamp: number
}

interface PauseState {
  isPaused: boolean
  remainingSeconds: number
}

const BUFFER_WINDOW = 300       // ms
const COUNT_WINDOW = 30000      // ms (30s)
const PAUSE_DURATION = 300000   // ms (5min)

let _instance: ReturnType<typeof _createAggregator> | null = null

function _createAggregator() {
  const buffer: BufferItem[] = []
  const warningErrors: number[] = []
  let paused = false
  let pausedUntil: number | null = null
  let flushTimer: ReturnType<typeof setTimeout> | null = null
  let _onShow: ((title: string, body: string, level: string) => void) | null = null

  // 从 localStorage 恢复暂停状态
  const saved = localStorage.getItem('notification_pause_state')
  if (saved) {
    try {
      const s = JSON.parse(saved)
      if (s.paused && s.pausedUntil > Date.now()) {
        paused = true
        pausedUntil = s.pausedUntil
      }
    } catch { /* ignore */ }
  }

  function extractTopic(title: string, _body: string): string {
    const lowered = title.toLowerCase()
    if (lowered.includes('完成') || lowered.includes('成功')) return 'done'
    if (lowered.includes('失败') || lowered.includes('异常') || lowered.includes('错误')) return 'error'
    if (lowered.includes('扫描')) return 'scan'
    if (lowered.includes('下载')) return 'download'
    if (lowered.includes('归档')) return 'archive'
    if (lowered.includes('查询')) return 'query'
    if (lowered.includes('备份')) return 'backup'
    if (lowered.includes('公告')) return 'announce'
    if (lowered.includes('更新') || lowered.includes('镜像')) return 'update'
    if (lowered.includes('IP') || lowered.includes('ip')) return 'ip'
    return '_' + (title.slice(0, 8) || 'default')
  }

  function savePauseState() {
    localStorage.setItem('notification_pause_state', JSON.stringify({
      paused, pausedUntil: pausedUntil ?? undefined,
    }))
  }

  function cleanWarningErrors(now: number) {
    for (let i = warningErrors.length - 1; i >= 0; i--) {
      if (now - warningErrors[i] > COUNT_WINDOW) warningErrors.splice(i, 1)
    }
  }

  function flush() {
    flushTimer = null
    if (buffer.length === 0) return

    const now = Date.now()
    // 按主题分组
    const groups = new Map<string, BufferItem[]>()
    for (const item of buffer) {
      const topic = extractTopic(item.title, item.body)
      if (!groups.has(topic)) groups.set(topic, [])
      groups.get(topic)!.push(item)
    }

    for (const [topic, items] of groups) {
      let title: string
      let body: string
      let level: string = items[0].level

      if (items.length === 1) {
        title = items[0].title
        body = items[0].body
      } else if (topic === 'done') {
        title = `${items.length} 项任务已完成`
        body = items.map(i => `· ${i.title}`).join('\n')
      } else if (topic === 'error') {
        title = `${items.length} 项操作出现异常`
        body = items.map(i => `· ${i.title}`).join('\n')
        level = 'warn'
      } else {
        title = `${items.length} 条 ${topic} 相关通知`
        body = items.map(i => `· ${i.title}`).join('\n')
      }

      if (level === 'warn' || level === 'error') {
        warningErrors.push(now)
        cleanWarningErrors(now)
        if (warningErrors.length >= 3) {
          paused = true
          pausedUntil = now + PAUSE_DURATION
          savePauseState()
          if (_onShow) {
            _onShow('通知已暂停', `连续 ${warningErrors.length} 次警告，通知将在 5 分钟后自动恢复`, 'warn')
          }
          return  // 不再显示本次合并的通知
        }
      }

      if (_onShow) _onShow(title, body, level)
    }
    buffer.length = 0
  }

  function shouldShow(level: string, title: string, body: string, onShow: (t: string, b: string, l: string) => void): boolean {
    _onShow = onShow
    if (paused) {
      if (pausedUntil && Date.now() >= pausedUntil) {
        paused = false
        pausedUntil = null
        savePauseState()
      } else {
        return false
      }
    }
    buffer.push({ level, title, body, timestamp: Date.now() })
    if (!flushTimer) {
      flushTimer = setTimeout(flush, BUFFER_WINDOW)
    }
    return false  // 总是等待缓冲窗口结束再显示
  }

  function getPauseState(): PauseState {
    return {
      isPaused: paused,
      remainingSeconds: paused && pausedUntil
        ? Math.max(0, Math.ceil((pausedUntil - Date.now()) / 1000))
        : 0,
    }
  }

  function resume() {
    paused = false
    pausedUntil = null
    savePauseState()
  }

  return { shouldShow, getPauseState, resume, _flush: flush }
}

export function useNotificationAggregator() {
  if (!_instance) _instance = _createAggregator()
  return _instance
}
