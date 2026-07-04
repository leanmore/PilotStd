// web/src/composables/useUserPreferences.ts
// 统一用户偏好读写层：localStorage 优先（页面秒开） → 后端兜底（跨设备同步）
import { ref, watch } from 'vue'
import { getItem, setItem } from '@/lib/storage'

// ── 键名映射 ──
const KEYS = {
  theme: 'theme',
  locale: 'locale',
  taskPath: 'task_path',
  toastConfig: 'notification_toast_config',
  quietHours: 'notification_quiet_hours',
  autoPause: 'notification_auto_pause',
} as const

function readLocal(key: string, fallback: unknown) {
  try {
    const raw = getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeLocal(key: string, value: unknown) {
  setItem(key, JSON.stringify(value))
}

// ── 单例状态 ──
const theme = ref<string>(readLocal(KEYS.theme, ''))
const locale = ref<string>(readLocal(KEYS.locale, 'zh-CN'))
const taskPath = ref<string>(readLocal(KEYS.taskPath, '/inbox'))
const toastConfig = ref<{ enabled: boolean; events: string[] }>(
  readLocal(KEYS.toastConfig, { enabled: true, events: ['auto_scan_failed', 'validity_system_failed', 'validity_standard_failed'] })
)
const quietHours = ref<{ enabled: boolean; start: string; end: string }>(
  readLocal(KEYS.quietHours, { enabled: false, start: '22:00', end: '07:00' })
)
const autoPause = ref<boolean>(readLocal(KEYS.autoPause, true))
const _initialized = ref(false)

let _syncTimer: ReturnType<typeof setTimeout> | null = null

function syncToBackend() {
  if (_syncTimer) clearTimeout(_syncTimer)
  _syncTimer = setTimeout(async () => {
    try {
      const { usePreferencesStore } = await import('@/stores/preferences')
      await usePreferencesStore().setAll({
        theme: theme.value,
        language: locale.value,
        task_path: taskPath.value,
        notification_toast_config: toastConfig.value,
        notification_quiet_hours: quietHours.value,
        notification_auto_pause: autoPause.value,
      })
    } catch { /* ignore */ }
  }, 500)
}

// 监听所有字段 → 写 localStorage + 防抖同步后端
watch(
  [theme, locale, taskPath, toastConfig, quietHours, autoPause],
  () => {
    writeLocal(KEYS.theme, theme.value)
    writeLocal(KEYS.locale, locale.value)
    writeLocal(KEYS.taskPath, taskPath.value)
    writeLocal(KEYS.toastConfig, toastConfig.value)
    writeLocal(KEYS.quietHours, quietHours.value)
    writeLocal(KEYS.autoPause, autoPause.value)
    if (_initialized.value) syncToBackend()
  },
  { deep: true },
)

/** 从后端拉取最新值覆盖本地（登录后调用一次） */
async function loadFromBackend() {
  if (_initialized.value) return
  _initialized.value = true

  try {
    const { usePreferencesStore } = await import('@/stores/preferences')
    const prefs = await usePreferencesStore().getAll()

    if (prefs.theme) theme.value = prefs.theme as string
    if (prefs.language) locale.value = prefs.language as string
    if (prefs.task_path) taskPath.value = prefs.task_path as string
    if (prefs.notification_toast_config) toastConfig.value = prefs.notification_toast_config as typeof toastConfig.value
    if (prefs.notification_quiet_hours) quietHours.value = prefs.notification_quiet_hours as typeof quietHours.value
    if (prefs.notification_auto_pause !== undefined) autoPause.value = prefs.notification_auto_pause as boolean

    // 同步回 localStorage
    writeLocal(KEYS.theme, theme.value)
    writeLocal(KEYS.locale, locale.value)
    writeLocal(KEYS.taskPath, taskPath.value)
    writeLocal(KEYS.toastConfig, toastConfig.value)
    writeLocal(KEYS.quietHours, quietHours.value)
    writeLocal(KEYS.autoPause, autoPause.value)

    // 一次性清理旧版 store 残留
    cleanupLegacy()
  } catch { /* 后端不可用，保持 localStorage 值 */ }
}

/** 一次性清理旧版 store 残留 */
function cleanupLegacy() {
  try { localStorage.removeItem('dashboard_widgets_visibility') } catch { /* ignore */ }
}

export function useUserPreferences() {
  return { theme, locale, taskPath, toastConfig, quietHours, autoPause, loadFromBackend, cleanupLegacy }
}
