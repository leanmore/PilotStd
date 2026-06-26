import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { THEMES, applyThemeToDom } from '@/config/themes'

export type ThemeId = keyof typeof THEMES

export const useAppStore = defineStore('app', () => {
  // 检测系统偏好，默认亮色
  const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const savedTheme = localStorage.getItem('theme') as ThemeId | null
  const defaultTheme: ThemeId = savedTheme || (sysDark ? 'dark' : 'light')
  const theme = ref<ThemeId>(defaultTheme)

  const locale = ref(localStorage.getItem('locale') || 'zh-CN')
  const loggedIn = ref(false)
  const username = ref('')

  // 主题切换：同步 CSS 变量 + data-theme 属性 + 持久化
  watch(theme, v => {
    const themeConfig = THEMES[v]
    if (themeConfig) {
      try {
        applyThemeToDom(themeConfig)
      } catch {
        // 测试环境或 SSR 时可能失败，静默忽略
      }
    }
    localStorage.setItem('theme', v)
  }, { immediate: true })

  watch(locale, v => localStorage.setItem('locale', v))

  // 系统主题变化时自动跟随（仅当用户未手动设置时）
  try {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      if (!localStorage.getItem('theme')) {
        theme.value = e.matches ? 'dark' : 'light'
      }
    })
  } catch {
    // 测试环境可能不支持
  }

  function setTheme(v: ThemeId) {
    theme.value = v
  }

  function toggleTheme() {
    // 在四套主题中循环切换
    const themeIds: ThemeId[] = ['light', 'dark', 'green', 'blue']
    const currentIndex = themeIds.indexOf(theme.value)
    theme.value = themeIds[(currentIndex + 1) % themeIds.length]
  }

  function setLocale(v: string) {
    locale.value = v
  }

  return { theme, locale, loggedIn, username, toggleTheme, setTheme, setLocale }
})
