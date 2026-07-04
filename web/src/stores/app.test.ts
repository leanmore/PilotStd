import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from './app'

describe('useAppStore', () => {
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
    store.theme = 'dark'
    await nextTick()
    expect(JSON.parse(localStorage.getItem('pilotstd_theme') || '""')).toBe('dark')
  })

  it('changing theme sets data-theme on document', async () => {
    const store = useAppStore()
    store.theme = 'dark'
    await nextTick()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('supports all four themes via theme assignment', async () => {
    const store = useAppStore()
    const themeIds = ['light', 'dark', 'green', 'blue'] as const
    for (const tid of themeIds) {
      store.theme = tid
      await nextTick()
      expect(store.theme).toBe(tid)
      expect(JSON.parse(localStorage.getItem('pilotstd_theme') || '""')).toBe(tid)
    }
  })

  it('theme watcher syncs to localStorage on change', async () => {
    const store = useAppStore()
    store.theme = 'green'
    await nextTick()
    expect(store.theme).toBe('green')
    expect(JSON.parse(localStorage.getItem('pilotstd_theme') || '""')).toBe('green')
  })
})
