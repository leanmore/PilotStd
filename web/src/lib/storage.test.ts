// lib/storage.test.ts — localStorage 统一命名空间 + 旧 key 迁移（NEW-44）
//
// userStorage.test.ts 测的是**用户隔离**存储；本文件测底层 `lib/storage.ts`：
//   · 所有读写落在 pilotstd_ 前缀（避免与宿主页面/浏览器扩展 key 冲突）；
//   · 旧无前缀 key 首次读取时迁移：返回旧值、写新 key、删旧 key；
//   · 新 key 已存在时不覆盖（保护更新数据）、旧值为空串也视为存在；
//   · removeItem 同时清新/旧 key；非迁移名单的旧数据不被擅自删除。
import { beforeEach, describe, expect, it } from 'vitest'
import { getItem, removeItem, setItem } from './storage'

/** 登记在 MIGRATIONS 里的旧 key（迁移名单本身也是契约） */
const LEGACY_KEYS = ['theme', 'locale', 'announce_tab', 'dashboard_layout']

describe('lib/storage：命名空间读写', () => {
  beforeEach(() => localStorage.clear())

  it('setItem/getItem 往返，落盘 key 带 pilotstd_ 前缀', () => {
    setItem('theme', 'dark')

    expect(getItem('theme')).toBe('dark')
    expect(localStorage.getItem('pilotstd_theme')).toBe('dark')
    // 不得再写裸 key（否则会与旧版迁移逻辑混淆）
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('未写入时返回 null；不同 key 互不干扰', () => {
    expect(getItem('theme')).toBeNull()
    expect(getItem('unknown_key')).toBeNull()

    setItem('theme', 'dark')
    setItem('locale', 'en')
    expect(getItem('theme')).toBe('dark')
    expect(getItem('locale')).toBe('en')
  })
})

describe('lib/storage：旧 key 迁移', () => {
  beforeEach(() => localStorage.clear())

  it('旧无前缀 key 首次读取即迁移：返回旧值、写新 key、删旧 key', () => {
    localStorage.setItem('theme', 'dark')

    expect(getItem('theme')).toBe('dark')
    expect(localStorage.getItem('pilotstd_theme')).toBe('dark')
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('四个登记过的旧 key 都会被迁移', () => {
    LEGACY_KEYS.forEach((key, i) => localStorage.setItem(key, `v${i}`))

    LEGACY_KEYS.forEach((key, i) => expect(getItem(key), key).toBe(`v${i}`))
    LEGACY_KEYS.forEach((key) => expect(localStorage.getItem(key), key).toBeNull())
  })

  it('新 key 已存在时不被旧值覆盖，旧 key 仍被清理，且读取返回**新值**', () => {
    localStorage.setItem('theme', 'legacy')
    localStorage.setItem('pilotstd_theme', 'newer')

    // 回归（2026-11-25）：原实现 migrate 无条件返回 oldVal，getItem 于是返回 'legacy'
    // 并删掉旧 key —— 更新的数据永远读不到。正确行为是返回新值。
    expect(getItem('theme')).toBe('newer')
    expect(localStorage.getItem('pilotstd_theme')).toBe('newer')
    expect(localStorage.getItem('theme')).toBeNull()
    expect(getItem('theme')).toBe('newer')
  })

  it('旧值为空串也视为存在并迁移（空串不等于“无数据”）', () => {
    localStorage.setItem('locale', '')

    expect(getItem('locale')).toBe('')
    expect(localStorage.getItem('pilotstd_locale')).toBe('')
    expect(localStorage.getItem('locale')).toBeNull()
  })

  it('迁移幂等：第二次读取直接命中新 key，不重复处理旧 key', () => {
    localStorage.setItem('theme', 'dark')

    expect(getItem('theme')).toBe('dark')
    expect(getItem('theme')).toBe('dark')
    // 只剩 pilotstd_theme 一个 key
    expect(localStorage.length).toBe(1)
  })

  it('非迁移名单的 key 不碰旧无前缀同名数据（不擅自删除未知旧 key）', () => {
    localStorage.setItem('custom', 'legacy-value')

    expect(getItem('custom')).toBeNull()
    expect(localStorage.getItem('custom')).toBe('legacy-value')
  })
})

describe('lib/storage：删除', () => {
  beforeEach(() => localStorage.clear())

  it('removeItem 同时清理新 key 与遗留旧 key', () => {
    localStorage.setItem('theme', 'old')
    setItem('theme', 'new')

    removeItem('theme')

    expect(localStorage.getItem('pilotstd_theme')).toBeNull()
    expect(localStorage.getItem('theme')).toBeNull()
    expect(getItem('theme')).toBeNull()
  })

  it('removeItem 对非迁移 key 只删新 key', () => {
    setItem('custom', 'v')

    removeItem('custom')

    expect(localStorage.getItem('pilotstd_custom')).toBeNull()
  })
})
