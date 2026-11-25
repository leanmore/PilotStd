// settings/constants.ts — 设置页 Tab 键表契约测试
//
// SETTINGS_TAB_KEYS 是 SettingsView 的 tab-bar 与 tabComponentMap 的唯一定义源：
// 少一个键 = 少一个 Tab；顺序错 = 入口顺序与用户预期不符；键重复 = 后一个组件覆盖前一个。
// 同时每个 key 必须在三种语言里都有标签（settings.tabs.<key>），否则 Tab 上会显示原始 key。
import { describe, it, expect } from 'vitest'
import { SETTINGS_TAB_KEYS } from './constants'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

const EXPECTED_ORDER = [
  'storage',
  'network',
  'query',
  'scan',
  'tasks',
  'ui',
  'ocr',
  'sites',
  'users',
  'token',
  'notification',
  'validity',
  'system',
] as const

const LOCALES = [
  ['zh-CN', zhCN],
  ['zh-TW', zhTW],
  ['en', en],
] as const

/** 按 path 读取 locale 里的标签，缺失返回 undefined */
function tabLabel(messages: unknown, key: string): unknown {
  const root = messages as { settings?: { tabs?: Record<string, unknown> } }
  return root.settings?.tabs?.[key]
}

describe('SETTINGS_TAB_KEYS 设置页 Tab 键表', () => {
  it('共 13 个 Tab，且顺序固定（顺序决定 tab-bar 的渲染次序）', () => {
    expect(SETTINGS_TAB_KEYS.length).toBe(13)
    expect([...SETTINGS_TAB_KEYS]).toEqual([...EXPECTED_ORDER])
  })

  it('键不重复（重复键会让 tabComponentMap 覆盖，等于丢一个页面）', () => {
    expect(new Set(SETTINGS_TAB_KEYS).size).toBe(SETTINGS_TAB_KEYS.length)
    for (const key of SETTINGS_TAB_KEYS) {
      expect(key, 'Tab key 必须是非空字符串').toMatch(/^[a-z][a-z0-9_]*$/)
    }
  })

  it('每个键在 zh-CN / zh-TW / en 都有非空标签，且不是 key 回显', () => {
    for (const key of SETTINGS_TAB_KEYS) {
      for (const [locale, messages] of LOCALES) {
        const label = tabLabel(messages, key)
        expect(typeof label, `${locale} 缺 settings.tabs.${key}`).toBe('string')
        expect(String(label).trim().length, `${locale} 的 settings.tabs.${key} 为空`).toBeGreaterThan(0)
        expect(label, `${locale} 的 settings.tabs.${key} 回显了 key`).not.toBe(key)
      }
    }
  })

  it('除通用缩写外，每个 Tab 的英文标签都与中文不同（确认标签真的走 i18n）', () => {
    for (const key of SETTINGS_TAB_KEYS) {
      // OCR 是中英共用的通用缩写，不参与「必须不同」断言
      if (key === 'ocr') continue
      expect(tabLabel(en, key), `settings.tabs.${key} 中英文案相同，疑似硬编码`).not.toBe(tabLabel(zhCN, key))
    }
    // 抽查 admin 专属 Tab：站点/用户/令牌必须存在，否则普通用户设置页缺入口
    for (const key of ['sites', 'users', 'token', 'system']) {
      expect(SETTINGS_TAB_KEYS).toContain(key)
    }
  })
})
