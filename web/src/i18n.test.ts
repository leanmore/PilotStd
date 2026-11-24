// i18n.test.ts — 全局 i18n 实例契约（NEW-44）
//
// 本模块被非组件模块（http 拦截器 / composable）直接使用，测四件事：
//   1. 启动语言来自 localStorage（legacy key 迁移由 lib/storage 负责，这里打桩）；
//   2. 兼容旧版 JSON.stringify 写入的带引号值（"\"zh-CN\"" → zh-CN）；
//   3. 三套语言包键集一致（漏翻 key 会退化成裸 key）；
//   4. 语言切换立即生效；未注册语言/缺失 key 的回退行为。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// 可控存储：getItem 每次返回当前值，配合 resetModules 模拟“不同本地存储启动”
const storage = vi.hoisted(() => ({ value: null as string | null }))
vi.mock('@/lib/storage', () => ({ getItem: () => storage.value }))

import { i18n, messages, savedLocale } from './i18n'

/** 重新加载模块（等价于刷新页面时重新初始化 i18n 单例） */
async function loadI18nWithStored(value: string | null) {
  storage.value = value
  vi.resetModules()
  return import('./i18n')
}

/** 展平语言包，得到点分 key 列表 */
function flatKeys(obj: Record<string, unknown>, prefix = '', out: string[] = []): string[] {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object') flatKeys(v as Record<string, unknown>, key, out)
    else out.push(key)
  }
  return out
}

let warnSpy: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
  storage.value = null
})

afterEach(() => {
  warnSpy.mockRestore()
  vi.resetModules()
})

describe('i18n 初始化', () => {
  it('无本地存储时默认 zh-CN，fallback 也是 zh-CN', () => {
    expect(savedLocale).toBe('zh-CN')
    expect(i18n.global.locale.value).toBe('zh-CN')
    expect(i18n.global.fallbackLocale.value).toBe('zh-CN')
  })

  it('本地存储的语言生效（en / zh-TW）', async () => {
    const en = await loadI18nWithStored('en')
    expect(en.savedLocale).toBe('en')
    expect(en.i18n.global.locale.value).toBe('en')

    const tw = await loadI18nWithStored('zh-TW')
    expect(tw.savedLocale).toBe('zh-TW')
    expect(tw.i18n.global.locale.value).toBe('zh-TW')
  })

  it('兼容旧版 JSON.stringify 写入的带引号值', async () => {
    const quoted = await loadI18nWithStored('"zh-TW"')
    expect(quoted.savedLocale).toBe('zh-TW')
    expect(quoted.i18n.global.locale.value).toBe('zh-TW')
  })

  it('三套语言包键集完全一致（漏翻 key 会退化成裸 key）', () => {
    expect(Object.keys(messages).sort()).toEqual(['en', 'zh-CN', 'zh-TW'])
    const zhKeys = flatKeys(messages['zh-CN'])
    expect(zhKeys.length).toBeGreaterThan(500)
    for (const locale of ['en', 'zh-TW'] as const) {
      expect(new Set(flatKeys(messages[locale])), locale).toEqual(new Set(zhKeys))
    }
  })
})

describe('i18n 运行时', () => {
  it('切换语言立即生效（同一实例不需要重建）', () => {
    i18n.global.locale.value = 'en'
    expect(i18n.global.t('nav.home')).toBe('Home')

    i18n.global.locale.value = 'zh-TW'
    expect(i18n.global.t('nav.home')).toBe('首頁')

    i18n.global.locale.value = 'zh-CN'
    expect(i18n.global.t('nav.home')).toBe('首页')
  })

  it('未注册的语言回退到 fallbackLocale（旧版本存储的未知 locale 不能白屏成裸 key）', () => {
    i18n.global.locale.value = 'fr'
    // 有中文兜底，而不是返回 key
    expect(i18n.global.t('nav.home')).toBe('首页')
  })

  it('语言包里不存在的 key 原样返回 key，不返回空串/undefined（便于排查拼写错误）', () => {
    const missing = '__missing__.key'
    expect(i18n.global.t(missing)).toBe(missing)
  })
})
