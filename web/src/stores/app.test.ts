import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from './app'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    // 清理 data-theme，避免 test 间污染
    document.documentElement.removeAttribute('data-theme')
  })

  it('default theme is light (system pref mock returns false)', () => {
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
    store.theme = 'dark'
    await nextTick()
    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('changing theme sets data-theme on document', async () => {
    const store = useAppStore()
    store.theme = 'dark'
    await nextTick()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
