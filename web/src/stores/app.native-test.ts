// Node.js 原生测试 — App Store（纯逻辑，无需 Vue SFC 编译）
import { describe, it, expect, beforeEach } from '../test-helper.js'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from './app'

describe('useAppStore (native)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('default theme is light', () => {
    const store = useAppStore()
    expect(store.theme).toBe('light')
  })

  it('default locale is zh-CN', () => {
    const store = useAppStore()
    expect(store.locale).toBe('zh-CN')
  })

  it('default loggedIn is false', () => {
    const store = useAppStore()
    expect(store.loggedIn).toBe(false)
  })

  it('changing theme persists to localStorage', async () => {
    const store = useAppStore()
    store.setTheme('dark')
    await nextTick()
    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('changing theme sets data-theme on document', async () => {
    const store = useAppStore()
    store.setTheme('dark')
    await nextTick()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('supports all four themes', async () => {
    const store = useAppStore()
    const themeIds = ['light', 'dark', 'green', 'blue'] as const
    for (const tid of themeIds) {
      store.setTheme(tid)
      await nextTick()
      expect(store.theme).toBe(tid)
      expect(document.documentElement.getAttribute('data-theme')).toBe(tid)
      expect(localStorage.getItem('theme')).toBe(tid)
    }
  })

  it('toggleTheme cycles through all four themes', async () => {
    const store = useAppStore()
    const expected = ['dark', 'green', 'blue', 'light']
    for (const exp of expected) {
      store.toggleTheme()
      await nextTick()
      expect(store.theme).toBe(exp)
    }
  })
})
