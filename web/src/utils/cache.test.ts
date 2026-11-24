// web/src/utils/cache.test.ts
// 会话级内存缓存（Q33：避免同会话内重复请求 /api/settings）契约测试。
//
// 契约边界说明：
//   1. 本模块是「纯会话级 Map 缓存」——没有 TTL、没有 LRU、没有容量上限。
//      TTL + LRU 的实现与测试在 @/composables/useApiCache（见 useApiCache.test.ts），
//      此处不重复造它的断言，而是锁定 sessionCache「不随时间/容量淘汰」的语义，
//      防止把两种缓存策略混在一个模块里。
//   2. get 未命中 / 存 null / 存 undefined 一律返回 null（?? null 归一），
//      但 0 / '' / false 是有效值，不能被当成未命中。
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { sessionCache } from './cache'

describe('sessionCache 读写契约', () => {
  beforeEach(() => {
    sessionCache.clear()
  })

  it('未写入的 key 返回 null（而不是 undefined），调用方可用 null 判空', () => {
    expect(sessionCache.get('missing')).toBeNull()
    expect(sessionCache.get('')).toBeNull()
  })

  it('存取各类值：对象 / 数组 / 字符串 / 数字', () => {
    const settings = { theme: 'dark', locale: 'zh-CN' }
    const list = [1, 2, 3]
    sessionCache.set('settings', settings)
    sessionCache.set('list', list)
    sessionCache.set('text', 'hello')
    sessionCache.set('number', 42)

    expect(sessionCache.get('settings')).toEqual({ theme: 'dark', locale: 'zh-CN' })
    expect(sessionCache.get('list')).toEqual([1, 2, 3])
    expect(sessionCache.get('text')).toBe('hello')
    expect(sessionCache.get('number')).toBe(42)
  })

  it('falsy 值原样返回：0 / 空串 / false 不算未命中', () => {
    sessionCache.set('zero', 0)
    sessionCache.set('empty', '')
    sessionCache.set('false', false)

    expect(sessionCache.get('zero')).toBe(0)
    expect(sessionCache.get('empty')).toBe('')
    expect(sessionCache.get('false')).toBe(false)
  })

  it('显式写入 null / undefined 时 get 统一回落 null（?? null）', () => {
    sessionCache.set('nullValue', null)
    sessionCache.set('undefinedValue', undefined)

    expect(sessionCache.get('nullValue')).toBeNull()
    expect(sessionCache.get('undefinedValue')).toBeNull()
  })

  it('同 key 重复写入以最新值为准', () => {
    sessionCache.set('k', 1)
    sessionCache.set('k', 2)
    expect(sessionCache.get('k')).toBe(2)
  })

  it('不同 key 相互隔离（含同前缀 key）', () => {
    sessionCache.set('settings', 'a')
    sessionCache.set('settings_extra', 'b')
    expect(sessionCache.get('settings')).toBe('a')
    expect(sessionCache.get('settings_extra')).toBe('b')
  })

  it('对象走引用而非克隆：取回的是同一个对象', () => {
    const obj = { a: 1 }
    sessionCache.set('obj', obj)
    const got = sessionCache.get<{ a: number }>('obj')
    expect(got).toBe(obj)
    got!.a = 2
    expect(sessionCache.get<{ a: number }>('obj')).toEqual({ a: 2 })
  })
})

describe('sessionCache 生命周期（会话级、无 TTL / 无 LRU）', () => {
  beforeEach(() => {
    sessionCache.clear()
  })

  it('clear 清空全部条目，之后同 key 返回 null', () => {
    sessionCache.set('a', 1)
    sessionCache.set('b', 2)
    expect(sessionCache._cache.size).toBe(2)

    sessionCache.clear()

    expect(sessionCache._cache.size).toBe(0)
    expect(sessionCache.get('a')).toBeNull()
    expect(sessionCache.get('b')).toBeNull()
  })

  it('时间流逝不失效（本模块无 TTL，会话内一直命中）', () => {
    vi.useFakeTimers()
    try {
      sessionCache.set('settings', { theme: 'dark' })
      vi.advanceTimersByTime(24 * 60 * 60 * 1000)
      expect(sessionCache.get('settings')).toEqual({ theme: 'dark' })
    } finally {
      vi.useRealTimers()
    }
  })

  it('写入量超过任何小容量也不会被淘汰（本模块无 LRU）', () => {
    const total = 100
    for (let i = 0; i < total; i++) sessionCache.set(`k-${i}`, i)

    expect(sessionCache._cache.size).toBe(total)
    for (let i = 0; i < total; i++) expect(sessionCache.get(`k-${i}`)).toBe(i)
  })
})
