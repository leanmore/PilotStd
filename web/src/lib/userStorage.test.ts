// web/src/lib/userStorage.test.ts
// 用户隔离 localStorage 契约测试：key 生成 / 解析、读写删除、默认值、
// 旧 key 迁移（幂等 / 新值优先 / 用户隔离）与脏数据容错（不 JSON.parse、原样返回）。
import { beforeEach, describe, expect, it } from 'vitest'

import {
  getUserItem,
  getUserKey,
  migrateLegacyPreferences,
  parseUserIdFromKey,
  removeUserItem,
  setUserItem,
} from './userStorage'

const LEGACY_KEYS = [
  'dashboard_layout',
  'pilotstd_dashboard_layout',
  'theme',
  'pilotstd_theme',
  'locale',
  'pilotstd_locale',
]

describe('getUserKey —— key 格式 user_{userId}_{key}', () => {
  it('按 userId 与偏好 key 拼接', () => {
    expect(getUserKey(1, 'theme')).toBe('user_1_theme')
    expect(getUserKey(42, 'dashboard_layout')).toBe('user_42_dashboard_layout')
    expect(getUserKey(0, 'locale')).toBe('user_0_locale')
  })
})

describe('parseUserIdFromKey —— 从 key 反解 userId', () => {
  it('合法 key 返回数字 userId', () => {
    expect(parseUserIdFromKey('user_1_theme')).toBe(1)
    expect(parseUserIdFromKey('user_42_dashboard_layout')).toBe(42)
    expect(parseUserIdFromKey('user_12_')).toBe(12)
  })

  it('多段 key 只取第一段作为 userId', () => {
    expect(parseUserIdFromKey('user_1_a_b')).toBe(1)
  })

  it('无前缀 / 缺分隔符 / 空 id / 非数字 id 返回 null', () => {
    expect(parseUserIdFromKey('dashboard_layout')).toBeNull()
    expect(parseUserIdFromKey('pilotstd_theme')).toBeNull()
    expect(parseUserIdFromKey('user_1')).toBeNull()
    expect(parseUserIdFromKey('user__theme')).toBeNull()
    expect(parseUserIdFromKey('user_abc_theme')).toBeNull()
    expect(parseUserIdFromKey('')).toBeNull()
  })

  it('负数 id 按 parseInt 原样返回（当前实现未校验正数，属已知边界）', () => {
    expect(parseUserIdFromKey('user_-5_theme')).toBe(-5)
  })
})

describe('用户隔离读写', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('未写入时 getUserItem 返回 null（默认值）', () => {
    expect(getUserItem(1, 'theme')).toBeNull()
    expect(localStorage.getItem('user_1_theme')).toBeNull()
  })

  it('setUserItem / getUserItem 往返，写入落到 user_{id}_{key}', () => {
    setUserItem(1, 'theme', 'dark')
    expect(getUserItem(1, 'theme')).toBe('dark')
    expect(localStorage.getItem('user_1_theme')).toBe('dark')
  })

  it('不同用户同 key 互不可见（用户隔离）', () => {
    setUserItem(1, 'theme', 'dark')
    setUserItem(2, 'theme', 'light')

    expect(getUserItem(1, 'theme')).toBe('dark')
    expect(getUserItem(2, 'theme')).toBe('light')
  })

  it('同用户同 key 重复写入覆盖旧值', () => {
    setUserItem(1, 'theme', 'dark')
    setUserItem(1, 'theme', 'light')
    expect(getUserItem(1, 'theme')).toBe('light')
  })

  it('removeUserItem 只删除目标用户目标 key', () => {
    setUserItem(1, 'theme', 'dark')
    setUserItem(2, 'theme', 'light')

    removeUserItem(1, 'theme')

    expect(getUserItem(1, 'theme')).toBeNull()
    expect(getUserItem(2, 'theme')).toBe('light')
    expect(localStorage.getItem('user_1_theme')).toBeNull()
  })

  it('脏数据容错：不做 JSON 解析，非法 JSON / "null" / 空串都原样返回', () => {
    setUserItem(1, 'layout', '{"a":')
    setUserItem(1, 'maybeNull', 'null')
    setUserItem(1, 'empty', '')

    expect(getUserItem(1, 'layout')).toBe('{"a":')
    expect(getUserItem(1, 'maybeNull')).toBe('null')
    expect(getUserItem(1, 'empty')).toBe('')
  })
})

describe('migrateLegacyPreferences —— 旧 key 迁移', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('旧的无前缀 key 迁移到用户隔离 key，并删除旧 key', () => {
    localStorage.setItem('theme', 'dark')

    migrateLegacyPreferences(1)

    expect(getUserItem(1, 'theme')).toBe('dark')
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('pilotstd_ 前缀旧 key 迁移时剥掉前缀', () => {
    localStorage.setItem('pilotstd_theme', 'light')

    migrateLegacyPreferences(1)

    expect(getUserItem(1, 'theme')).toBe('light')
    expect(localStorage.getItem('pilotstd_theme')).toBeNull()
  })

  it('六种旧 key 全部迁移到三个隔离 key', () => {
    localStorage.setItem('dashboard_layout', 'layout-a')
    localStorage.setItem('theme', 'dark')
    localStorage.setItem('locale', 'zh-CN')

    migrateLegacyPreferences(1)

    expect(getUserItem(1, 'dashboard_layout')).toBe('layout-a')
    expect(getUserItem(1, 'theme')).toBe('dark')
    expect(getUserItem(1, 'locale')).toBe('zh-CN')
    for (const legacyKey of LEGACY_KEYS) expect(localStorage.getItem(legacyKey)).toBeNull()
  })

  it('幂等：重复迁移不改变已迁移的值，也不重复建 key', () => {
    localStorage.setItem('theme', 'dark')
    migrateLegacyPreferences(1)
    const sizeAfterFirst = localStorage.length

    migrateLegacyPreferences(1)

    expect(getUserItem(1, 'theme')).toBe('dark')
    expect(localStorage.length).toBe(sizeAfterFirst)
  })

  it('新 key 已存在时跳过该组迁移，旧值不覆盖新值', () => {
    setUserItem(1, 'theme', 'new-value')
    localStorage.setItem('theme', 'legacy-value')

    migrateLegacyPreferences(1)

    expect(getUserItem(1, 'theme')).toBe('new-value')
  })

  it('没有旧 key 时不创建任何新 key', () => {
    migrateLegacyPreferences(1)
    expect(localStorage.length).toBe(0)
  })

  it('迁移只作用于指定 userId；旧 key 被消费后另一用户不会继承', () => {
    localStorage.setItem('theme', 'dark')
    migrateLegacyPreferences(1)

    migrateLegacyPreferences(2)

    expect(getUserItem(1, 'theme')).toBe('dark')
    expect(getUserItem(2, 'theme')).toBeNull()
  })

  it('旧值为空串（非 null）也视为存在并迁移', () => {
    localStorage.setItem('theme', '')

    migrateLegacyPreferences(1)

    expect(getUserItem(1, 'theme')).toBe('')
    expect(localStorage.getItem('theme')).toBeNull()
  })
})
