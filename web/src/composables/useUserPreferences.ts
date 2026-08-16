// web/src/composables/useUserPreferences.ts
// 统一用户偏好读写层：localStorage 优先（页面秒开） → 后端兜底（跨设备同步）

import { ref, watch } from 'vue'
import { getItem, setItem } from '@/lib/storage'

const KEYS = {
  theme: 'theme',
  locale: 'locale',
  taskPath: 'task_path',
  quietHours: 'notification_quiet_hours',
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

// 字符串字段透明读写（不 JSON 序列化），兼容旧版 JSON.stringify 写入的带引号值
function readPlainString(key: string, fallback: string): string {
  const raw = getItem(key)
  if (!raw) return fallback
  return raw.startsWith('"') ? raw.replace(/^"|"$/g, '') : raw
}

const theme = ref<string>(readLocal(KEYS.theme, ''))
const locale = ref<string>(readPlainString(KEYS.locale, 'zh-CN'))
const taskPath = ref<string>(readLocal(KEYS.taskPath, '/inbox'))
const quietHours = ref<{ enabled: boolean; start: string; end: string }>(
  readLocal(KEYS.quietHours, { enabled: false, start: '22:00', end: '07:00' }),
)
const _initialized = ref(false)

let _syncTimer: ReturnType<typeof setTimeout> | null = null

function syncToBackend() {
  if (_syncTimer) clearTimeout(_syncTimer)
  _syncTimer = setTimeout(async () => {
    try {
      const { usePreferencesStore } = await import('@/stores/preferences')
      await usePreferencesStore().setAll({
        ui: { theme: theme.value, language: locale.value },
        task_path: taskPath.value,
        notification_quiet_hours: quietHours.value,
      })
    } catch { /* ignore */ }
  }, 500)
}

watch(
  [theme, locale, taskPath, quietHours],
  () => {
    writeLocal(KEYS.theme, theme.value)
    setItem(KEYS.locale, locale.value)
    writeLocal(KEYS.taskPath, taskPath.value)
    writeLocal(KEYS.quietHours, quietHours.value)
    if (_initialized.value) syncToBackend()
  },
  { deep: true },
)

async function loadFromBackend() {
  if (_initialized.value) return
  _initialized.value = true

  try {
    const { usePreferencesStore } = await import('@/stores/preferences')
    const prefs = await usePreferencesStore().getAll()

    const ui = (prefs.ui as Record<string, unknown>) || {}
    if (ui.theme) theme.value = ui.theme as string
    if (ui.language) locale.value = ui.language as string
    if (prefs.task_path) taskPath.value = prefs.task_path as string
    if (prefs.notification_quiet_hours) quietHours.value = prefs.notification_quiet_hours as typeof quietHours.value

    writeLocal(KEYS.theme, theme.value)
    setItem(KEYS.locale, locale.value)
    writeLocal(KEYS.taskPath, taskPath.value)
    writeLocal(KEYS.quietHours, quietHours.value)

    cleanupLegacy()
  } catch { /* 后端不可用，保持 localStorage 值 */ }
}

function cleanupLegacy() {
  try {
    localStorage.removeItem('dashboard_widgets_visibility')
  } catch { /* ignore */ }
}

export function useUserPreferences() {
  return { theme, locale, taskPath, quietHours, loadFromBackend, cleanupLegacy }
}
