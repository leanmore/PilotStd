import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import http from '@/api/http'
import { THEMES, applyThemeToDom } from '@/config/themes'
import { useUserPreferences } from '@/composables/useUserPreferences'
import { migrateLegacyPreferences } from '@/lib/userStorage'

export type ThemeId = keyof typeof THEMES

export const useAppStore = defineStore('app', () => {
  const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const { theme: prefsTheme, locale: prefsLocale, loadFromBackend } = useUserPreferences()

  const defaultTheme: ThemeId = (prefsTheme.value as ThemeId) || (sysDark ? 'dark' : 'light')
  const theme = ref<ThemeId>(defaultTheme)
  const locale = ref(prefsLocale.value || 'zh-CN')
  const loggedIn = ref(false)
  const userId = ref(0)
  const username = ref('')
  const role = ref('user')
  const dashboardLocked = ref(true)
  const _initialized = ref(false)

  /** 从后端拉取偏好并覆盖本地（登录后调用） */
  async function loadPreferences() {
    if (!loggedIn.value) return
    if (_initialized.value) return

    try {
      await loadFromBackend()

      if (prefsTheme.value && prefsTheme.value in THEMES) {
        theme.value = prefsTheme.value as ThemeId
      }
      if (prefsLocale.value) {
        locale.value = prefsLocale.value
      }
    } catch { /* 保持 localStorage 值 */ }

    // 安全恢复身份：从服务端 JWT 获取，禁止信任客户端存储
    try {
      const { data } = await http.get('/auth/me')
      if (data.id) {
        userId.value = data.id
        migrateLegacyPreferences(data.id)
      }
      if (data.role) {
        role.value = data.role
      }
      if (data.username) {
        username.value = data.username
      }
    } catch { /* 未登录或 token 过期，保持默认值 */ }
    _initialized.value = true
  }

  // 登录成功后自动触发偏好拉取（覆盖显式登录与已登录直接访问两种场景）
  watch(loggedIn, (v) => { if (v) loadPreferences() })

  /** 清除用户状态（登出时调用） */
  function clearUser() {
    loggedIn.value = false
    userId.value = 0
    username.value = ''
    role.value = 'user'
    dashboardLocked.value = true
    _initialized.value = false
  }

  /** 切换仪表盘布局锁定状态 */
  function toggleDashboardLock() {
    dashboardLocked.value = !dashboardLocked.value
  }

  watch(theme, v => {
    const tc = THEMES[v]
    if (tc) { try { applyThemeToDom(tc) } catch { /* SSR */ } }
    prefsTheme.value = v
  }, { immediate: true })

  watch(locale, v => { prefsLocale.value = v })

  try {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      if (!prefsTheme.value) theme.value = e.matches ? 'dark' : 'light'
    })
  } catch { /* SSR */ }

  return { theme, locale, loggedIn, userId, username, role, dashboardLocked, loadPreferences, clearUser, toggleDashboardLock }
})
