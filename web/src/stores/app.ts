import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 检测系统偏好，默认亮色
  const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const savedTheme = localStorage.getItem('theme')
  const theme = ref(savedTheme || (sysDark ? 'dark' : 'light'))

  const locale = ref(localStorage.getItem('locale') || 'zh-CN')
  const loggedIn = ref(false)
  const username = ref('')

  // 主题切换：同步 data-theme 属性 + 持久化
  watch(theme, v => {
    document.documentElement.setAttribute('data-theme', v)
    localStorage.setItem('theme', v)
  }, { immediate: true })

  watch(locale, v => localStorage.setItem('locale', v))

  // 系统主题变化时自动跟随（仅当用户未手动设置时）
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem('theme')) {
      theme.value = e.matches ? 'dark' : 'light'
    }
  })

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, locale, loggedIn, username, toggleTheme }
})
