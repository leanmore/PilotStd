import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { THEMES, applyThemeToDom } from '@/config/themes'

export type ThemeId = keyof typeof THEMES

export const useAppStore = defineStore('app', () => {
  const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const savedTheme = localStorage.getItem('theme') as ThemeId | null
  const defaultTheme: ThemeId = savedTheme || (sysDark ? 'dark' : 'light')
  const theme = ref<ThemeId>(defaultTheme)

  const savedLocale = localStorage.getItem('locale')
  const locale = ref(savedLocale || 'zh-CN')
  const loggedIn = ref(false)
  const username = ref('')
  const _initialized = ref(false)

  /** 从 preferencesStore 加载持久化配置（登录后调用） */
  async function loadPreferences() {
    if (_initialized.value) return
    _initialized.value = true

    try {
      const { usePreferencesStore } = await import('./preferences')
      const prefs = usePreferencesStore()

      const backendTheme = await prefs.get<string>('theme')
      if (backendTheme && backendTheme in THEMES) {
        theme.value = backendTheme as ThemeId
      }

      const backendLang = await prefs.get<string>('language')
      if (backendLang) {
        locale.value = backendLang
        localStorage.setItem('locale', backendLang)
      }
    } catch {
      // preferencesStore 不可用时保持 localStorage 值
    }
  }

  // 主题切换：同步 CSS + localStorage + 后端
  watch(theme, async v => {
    const themeConfig = THEMES[v]
    if (themeConfig) {
      try { applyThemeToDom(themeConfig) } catch { /* SSR */ }
    }
    localStorage.setItem('theme', v)
    // 异步同步到后端
    try {
      const { usePreferencesStore } = await import('./preferences')
      usePreferencesStore().set('theme', v).catch(() => {})
    } catch { /* ignore */ }
  }, { immediate: true })

  watch(locale, async v => {
    localStorage.setItem('locale', v)
    try {
      const { usePreferencesStore } = await import('./preferences')
      usePreferencesStore().set('language', v).catch(() => {})
    } catch { /* ignore */ }
  })

  // 系统主题变化自动跟随
  try {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      if (!localStorage.getItem('theme')) {
        theme.value = e.matches ? 'dark' : 'light'
      }
    })
  } catch { /* SSR */ }

  return { theme, locale, loggedIn, username, loadPreferences }
})
