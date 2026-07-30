import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import axios from 'axios'
import { THEMES, applyThemeToDom } from '@/config/themes'
import { useUserPreferences } from '@/composables/useUserPreferences'

export type ThemeId = keyof typeof THEMES

export const useAppStore = defineStore('app', () => {
  const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const { theme: prefsTheme, locale: prefsLocale, loadFromBackend } = useUserPreferences()

  const defaultTheme: ThemeId = (prefsTheme.value as ThemeId) || (sysDark ? 'dark' : 'light')
  const theme = ref<ThemeId>(defaultTheme)
  const locale = ref(prefsLocale.value || 'zh-CN')
  const loggedIn = ref(false)
  const username = ref('')
  const role = ref('user')
  const _initialized = ref(false)

  /** 从后端拉取偏好并覆盖本地（登录后调用） */
  async function loadPreferences() {
    if (_initialized.value) return
    _initialized.value = true

    try {
      await loadFromBackend()

      if (prefsTheme.value && prefsTheme.value in THEMES) {
        theme.value = prefsTheme.value as ThemeId
      }
      if (prefsLocale.value) {
        locale.value = prefsLocale.value
      }
    } catch { /* 保持 localStorage 值 */ }

    // 安全恢复角色：从服务端 JWT 获取，禁止信任客户端存储
    try {
      const { data } = await axios.get('/api/auth/me')
      if (data.role) {
        role.value = data.role
      }
      if (data.username) {
        username.value = data.username
      }
    } catch { /* 未登录或 token 过期，保持默认值 */ }
  }

  /** 清除用户状态（登出时调用） */
  function clearUser() {
    loggedIn.value = false
    username.value = ''
    role.value = 'user'
    _initialized.value = false
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

  return { theme, locale, loggedIn, username, role, loadPreferences, clearUser }
})
