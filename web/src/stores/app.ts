import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
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

  return { theme, locale, loggedIn, username, role, loadPreferences }
})
