/**
 * 设计令牌回归守卫（对应 2026-11-21 的 D1–D4 修复）。
 *
 * 锁住四条结论，谁改回去这里就红：
 *  1. `web/src` 内 `var()` 不得引用未定义变量——修复前 11 个变量名 / 26 处引用，
 *     后果是深色主题下 NotificationBell 恒为浅色、两处键盘焦点轮廓整条声明失效；
 *  2. `style.css` 的默认令牌层必须与 `themes.ts` 的 light 主题一致——
 *     修复前 `--bg` 与 `--surface-raised` 两两互换，首屏（JS 注入前）层级颠倒；
 *  3. 不得再引用已失效的调研文档路径（`docs/.local/archive/` 下的归档路径除外）；
 *  4. `styles/design-tokens.css` 只放主题无关令牌：无颜色字面量、不覆盖旧 `--radius-*`。
 *
 * 说明：本文件只做静态扫描，不启动浏览器；与 a11y-contrast.test.ts 的分工是
 * 「那测对比度取值是否正确，这测令牌引用是否成立」。
 */
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { THEMES } from '../config/themes'

// Vitest 在本仓以 CJS 风格注入 __dirname（与 a11y-contrast.test.ts 一致）；
// 不用 import.meta.url：该环境下的 URL 不是 file: 协议，fileURLToPath 会抛错。
const SRC = resolve(__dirname, '..')
const SCAN_EXT = ['.vue', '.css', '.ts']

/** 递归收集 src 下参与扫描的文件（排除测试自身） */
function collect(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules') continue
      collect(full, out)
    } else if (SCAN_EXT.some((ext) => entry.name.endsWith(ext)) && !entry.name.endsWith('.test.ts')) {
      out.push(full)
    }
  }
  return out
}

const FILES = collect(SRC)
const relative = (p: string): string => p.slice(SRC.length + 1).replace(/\\/g, '/')

/** 读取文件并保留行号，报错时能直接定位 */
function lines(file: string): string[] {
  return readFileSync(file, 'utf8').split(/\r?\n/)
}

describe('令牌引用完整性（D1）', () => {
  it('web/src 内不存在引用未定义 CSS 变量的 var()', () => {
    const defined = new Set<string>()
    for (const file of FILES) {
      const text = readFileSync(file, 'utf8')
      // CSS 声明：行首/空白后的 --name:
      for (const m of text.matchAll(/(?:^|\s)(--[a-zA-Z0-9_-]+)\s*:/g)) defined.add(m[1])
      // themes.ts 运行时注入：'--name': c.xxx
      for (const m of text.matchAll(/'(--[a-zA-Z0-9_-]+)'\s*:\s*c\./g)) defined.add(m[1])
      // useThemeSync 注入：setProperty('--name', ...)
      for (const m of text.matchAll(/setProperty\(\s*'(--[a-zA-Z0-9_-]+)'/g)) defined.add(m[1])
    }

    const offenders: string[] = []
    for (const file of FILES) {
      lines(file).forEach((line, idx) => {
        for (const m of line.matchAll(/var\(\s*(--[a-zA-Z0-9_-]+)/g)) {
          const name = m[1]
          // --p-* 由 PrimeVue Aura 运行时提供，不在本仓定义集合内
          if (name.startsWith('--p-')) continue
          if (!defined.has(name)) offenders.push(`${relative(file)}:${idx + 1} → var(${name})`)
        }
      })
    }
    expect(offenders, `未定义变量引用:\n${offenders.join('\n')}`).toEqual([])
  })
})

describe('默认令牌层与运行层一致（D2）', () => {
  it('style.css 的 :root 默认值与 themes.ts light 主题一一对应', () => {
    const css = readFileSync(resolve(SRC, 'style.css'), 'utf8')
    const rootBlock = css.slice(css.indexOf(':root'), css.indexOf('}', css.indexOf(':root')))
    const readVar = (name: string): string => {
      const m = rootBlock.match(new RegExp(`${name}\\s*:\\s*([^;]+);`))
      return m ? m[1].replace(/\s/g, '').toLowerCase() : ''
    }
    const light = THEMES.light.colors
    expect(readVar('--bg')).toBe(light.bg.toLowerCase())
    expect(readVar('--surface')).toBe(light.surface.toLowerCase())
    expect(readVar('--surface-raised')).toBe(light.surfaceRaised.toLowerCase())
    expect(readVar('--border')).toBe(light.border.toLowerCase())
  })
})

describe('文档引用有效（D4）', () => {
  it('不再引用已失效的调研文档路径（归档路径除外）', () => {
    const offenders: string[] = []
    for (const file of FILES) {
      lines(file).forEach((line, idx) => {
        if (!line.includes('aura-token-sync-feasibility')) return
        // 允许指向 docs/.local/archive/ 的归档说明
        if (line.includes('docs/.local/archive')) return
        offenders.push(`${relative(file)}:${idx + 1}`)
      })
    }
    expect(offenders, `失效引用:\n${offenders.join('\n')}`).toEqual([])
  })
})

describe('design-tokens.css 的边界（Q1 锁定）', () => {
  const tokenFile = resolve(SRC, 'styles/design-tokens.css')
  const css = readFileSync(tokenFile, 'utf8')

  it('不含任何颜色字面量', () => {
    expect(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([])
    expect(css.match(/\brgba?\(/g) ?? []).toEqual([])
    expect(css.match(/\bhsla?\(/g) ?? []).toEqual([])
  })

  it('不覆盖旧圆角令牌（--radius / --radius-sm / --radius-lg）', () => {
    expect(css.match(/^\s*--radius(?:-sm|-lg)?\s*:/gm) ?? []).toEqual([])
  })

  it('提供尺度层关键令牌', () => {
    for (const name of [
      '--space-4', '--space-16', '--font-size-13', '--font-size-h1',
      '--line-height-body', '--font-weight-semibold',
      '--ds-radius-md', '--ds-radius-pill', '--icon-tile-md', '--btn-height-md',
    ]) {
      expect(css).toContain(`${name}:`)
    }
  })
})
