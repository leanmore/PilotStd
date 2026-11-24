// config/themes.test.ts — 主题注册表与 DOM 注入契约（NEW-44）
//
// theme-spec / a11y-contrast 测的是“配色数值是否达标”，本文件测**主题结构与运行时注入**：
//   · 四套主题的 id / labelKey / type 与 isDarkTheme 判定一致（列表与判定不能两套口径）；
//   · applyThemeToDom 把 colors 的每个键按 camelCase→kebab-case 写成同名 CSS 变量
//     （ThemeConfig 声明了却不注入就是死键，A-53 曾出现）；
//   · 兼容别名 --accent* 指向 primary 系列；
//   · 切换主题是覆盖写，data-theme 保持单值，四套主题底色互不相同。
import { afterEach, describe, expect, it } from 'vitest'
import { DARK_THEME_IDS, THEMES, applyThemeToDom, isDarkTheme } from './themes'

const root = () => document.documentElement
const cssVar = (name: string) => root().style.getPropertyValue(name)
/** 与源码注入表的命名约定一致：camelCase → kebab-case */
const kebab = (key: string) => key.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)

afterEach(() => {
  root().removeAttribute('data-theme')
  root().removeAttribute('style')
})

describe('主题注册表', () => {
  it('四套主题 id / labelKey / type 与 isDarkTheme 判定一致', () => {
    expect(Object.keys(THEMES).sort()).toEqual(['blue', 'dark', 'green', 'light'])
    for (const [id, theme] of Object.entries(THEMES)) {
      expect(theme.id, id).toBe(id)
      // 主题名走 i18n：只存 key，禁止硬编码中文/英文名
      expect(theme.labelKey, id).toBe(`settings.theme.${id}`)
      expect(theme.type === 'dark', id).toBe(isDarkTheme(id))
    }
  })

  it('暗色主题集合固定为 dark / blue，未知 id 不判为暗色', () => {
    expect([...DARK_THEME_IDS].sort()).toEqual(['blue', 'dark'])
    expect(isDarkTheme('light')).toBe(false)
    expect(isDarkTheme('green')).toBe(false)
    expect(isDarkTheme('unknown')).toBe(false)
  })
})

describe('applyThemeToDom', () => {
  it('写入 data-theme，且 colors 每个键都注入同名 CSS 变量（无死键）', () => {
    for (const id of Object.keys(THEMES)) {
      applyThemeToDom(THEMES[id])
      expect(root().getAttribute('data-theme'), id).toBe(id)
      for (const [key, value] of Object.entries(THEMES[id].colors)) {
        expect(cssVar(`--${kebab(key)}`), `${id}.${key} 未注入 DOM`).toBe(value)
      }
    }
  })

  it('向后兼容别名 --accent* 指向 primary 系列', () => {
    applyThemeToDom(THEMES.blue)
    const c = THEMES.blue.colors
    expect(cssVar('--accent')).toBe(c.primary)
    expect(cssVar('--accent-dim')).toBe(c.primaryHover)
    expect(cssVar('--accent-bg')).toBe(c.primaryBg)
    expect(cssVar('--accent-border')).toBe(c.primaryBorder)
  })

  it('切换主题是覆盖写：不残留旧主题值，data-theme 保持单值', () => {
    applyThemeToDom(THEMES.light)
    const lightBg = cssVar('--bg')

    applyThemeToDom(THEMES.dark)

    expect(cssVar('--bg')).toBe(THEMES.dark.colors.bg)
    expect(cssVar('--bg')).not.toBe(lightBg)
    expect(root().getAttribute('data-theme')).toBe('dark')
    expect(root().getAttribute('data-theme')).not.toContain('light')
  })

  it('四套主题主背景色互不相同（切换肉眼可见）', () => {
    const bgs = new Set<string>()
    for (const id of Object.keys(THEMES)) {
      applyThemeToDom(THEMES[id])
      bgs.add(cssVar('--bg'))
    }
    expect(bgs.size).toBe(4)
  })
})
