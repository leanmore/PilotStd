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
 * 2026-11-22（模块一）：A-53 接线完成——`disabledBg`/`disabledText` 已由
 * `applyThemeToDom` 注入 `--disabled-bg`/`--disabled-text`，不再是死键；本文件
 * 因此把这两个键从 `UNWIRED_KEYS` 移除，并新增「四主题禁用态对比度 ≥3:1」契约。
 * 禁用态文字属 WCAG 1.4.3 的 inactive component 豁免范围，但本仓仍要求 ≥3:1
 * （与 1.4.11 非文本对比度同档），避免"看不清的灰字"变成可用性缺陷。
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

/** 从 `applyThemeToDom` 源码解析 `'--var': c.prop` 映射（单一真相来源，D2 与 A-53 共用） */
function cssVarMapping(): Array<[string, string]> {
  const src = readFileSync(resolve(SRC, 'config/themes.ts'), 'utf8')
  const pairs: Array<[string, string]> = []
  for (const m of src.matchAll(/'(--[a-zA-Z0-9_-]+)'\s*:\s*c\.([a-zA-Z0-9_]+)/g)) {
    pairs.push([m[1], m[2]])
  }
  return pairs
}

/** 解析 `style.css` 的 `:root` 声明为 {变量名 → 归一化取值}（别名最多展开 3 层） */
function rootVars(): Map<string, string> {
  const css = readFileSync(resolve(SRC, 'style.css'), 'utf8')
  const rootBlock = css.slice(css.indexOf(':root'), css.indexOf('}', css.indexOf(':root')))
  const out = new Map<string, string>()
  for (const m of rootBlock.matchAll(/(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);/g)) {
    out.set(m[1], m[2].replace(/\s/g, '').toLowerCase())
  }
  // 解析别名（--accent: var(--primary)）：最多展开 3 层，避免环
  const resolveAlias = (v: string, depth = 0): string => {
    const alias = v.match(/^var\((--[a-zA-Z0-9_-]+)\)$/)
    if (!alias || depth >= 3) return v
    const target = out.get(alias[1])
    return target === undefined ? v : resolveAlias(target, depth + 1)
  }
  for (const [k, v] of out) out.set(k, resolveAlias(v))
  return out
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

describe('默认令牌层与运行层一致（D2，2026-11-21 扩到全量映射）', () => {
  const COLOR_RE = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\))$/i

  // 已知未接线的颜色键：目前为空。
  // A-53（disabledBg/disabledText）已于 2026-11-22 接线并移出本集合；后续若再出现
  // 「ThemeConfig 声明了但 applyThemeToDom/style.css 都没接」的死键，登记到这里并同步
  // docs/debt/03-open.md，不得靠删键掩盖。
  const UNWIRED_KEYS = new Set<string>([])

  it('映射表覆盖 themes.ts 的颜色键（除已登记死键外不漏接线）', () => {
    const mapped = new Set(cssVarMapping().map(([, prop]) => prop))
    const missing = Object.keys(THEMES.light.colors).filter((k) => !mapped.has(k) && !UNWIRED_KEYS.has(k))
    expect(missing, `未接入 CSS 变量的颜色键: ${missing.join(', ')}`).toEqual([])
  })

  it('映射表里的每个 prop 在四主题都存在（防重命名漏改）', () => {
    for (const [cssVar, prop] of cssVarMapping()) {
      for (const id of ['light', 'dark', 'green', 'blue']) {
        expect(prop in (THEMES[id].colors as Record<string, unknown>), `${id}.${prop} (${cssVar})`).toBe(true)
      }
    }
  })

  it('四个主题的每个映射值都是非空合法颜色（含 dark/green/blue）', () => {
    const pairs = cssVarMapping()
    expect(pairs.length).toBeGreaterThan(20)
    for (const id of ['light', 'dark', 'green', 'blue']) {
      const colors = THEMES[id].colors as unknown as Record<string, string>
      for (const [cssVar, prop] of pairs) {
        const value = colors[prop]
        expect(typeof value, `${id}.${prop}`).toBe('string')
        expect(value.length, `${id}.${prop} 为空`).toBeGreaterThan(0)
        // 只有“颜色型”值才做形态校验；focusRing 是 box-shadow 串，不套颜色正则
        if (value.startsWith('#') || value.startsWith('rgb')) {
          expect(COLOR_RE.test(value), `${id}.${prop}=${value} 不是合法颜色`).toBe(true)
        }
        expect(value, `${cssVar} 在 ${id} 未接线`).toBeTruthy()
      }
    }
  })

  it('style.css 的 :root 默认值与 light 主题全量一致（不止 4 个）', () => {
    const root = rootVars()
    const light = THEMES.light.colors as unknown as Record<string, string>
    const mismatched: string[] = []
    for (const [cssVar, prop] of cssVarMapping()) {
      const expected = (light[prop] || '').replace(/\s/g, '').toLowerCase()
      const actual = root.get(cssVar)
      // 默认层未声明的变量（由 JS 专供的主题令牌）跳过——它们不属于“默认层”
      if (actual === undefined) continue
      if (actual !== expected) mismatched.push(`${cssVar}: CSS=${actual} vs light=${expected}`)
    }
    expect(mismatched, `默认层与 light 漂移:\n${mismatched.join('\n')}`).toEqual([])
  })
})

/**
 * A-53 接线契约（2026-11-22，模块一）。
 *
 * 三条一起锁：
 *  1. `applyThemeToDom` 确实映射了 `--disabled-bg` / `--disabled-text`（不是只声明在 ThemeConfig 里）；
 *  2. `style.css` 的默认层也声明了同名变量（首屏 JS 注入前不会回退到 undefined → 透明）；
 *  3. 四主题的禁用态文字对禁用态底色 ≥ 3:1。
 *
 * 第 3 条的阈值与豁免（重要，改前先读）：
 *   - 禁用态文字按 WCAG 1.4.3 属 "inactive user interface component"，**没有** 4.5:1 要求；
 *     本仓取 3:1（与 1.4.11 非文本对比度同档），目标是"灰得看得见"，不是"可长期阅读"。
 *   - 当前 light(2.08) / dark(2.96) / blue(1.93) 三套的令牌取值达不到 3:1，
 *     而 light 的 `#e2e8f0` / `#94a3b8` 又被 D2 默认层一致性钉死、P2 约束禁止为过测试改值。
 *     故把这三套登记为 `DISABLED_CONTRAST_EXEMPT` 并记录实测值：
 *     **调低任何已登记主题的对比度、或新增主题落在 3:1 以下却没登记，这里都会红。**
 *   - green(4.38) 达标，不在豁免表内——它是这条断言的"活样本"，防止阈值被悄悄放宽。
 */
describe('禁用态令牌接线与对比度（A-53，2026-11-22）', () => {
  /** sRGB 相对亮度（与 a11y-contrast.test.ts 同一算法，此处内联以免测试文件互相 import） */
  function srgb(v: number): number {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  }

  function luminance(hex: string): number {
    const h = hex.replace('#', '')
    return (
      0.2126 * srgb(parseInt(h.slice(0, 2), 16)) +
      0.7152 * srgb(parseInt(h.slice(2, 4), 16)) +
      0.0722 * srgb(parseInt(h.slice(4, 6), 16))
    )
  }

  /** WCAG 对比度（1~21） */
  function contrast(a: string, b: string): number {
    const l1 = luminance(a)
    const l2 = luminance(b)
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
  }

  /** 禁用态文字的最低对比度（WCAG 1.4.3 对 inactive 组件无要求，本仓自定 3:1） */
  const DISABLED_MIN_CONTRAST = 3

  /**
   * 已登记的不达标主题 → 实测对比度（保留两位，便于 diff 时一眼看出是否被改低）。
   * 修值后请把该主题从这里删掉，让断言重新接管（删行即收紧，不需要改阈值）。
   */
  const DISABLED_CONTRAST_EXEMPT: Record<string, number> = {
    light: 2.08, // #94a3b8 on #e2e8f0（被 D2 默认层一致性钉死，见上方说明）
    dark: 2.96, // #94a3b8 on #475569
    blue: 1.93, // #475569 on #1e293b
  }

  const THEME_IDS = ['light', 'dark', 'green', 'blue'] as const

  it('applyThemeToDom 已映射 --disabled-bg / --disabled-text', () => {
    const mapped = new Map(cssVarMapping())
    expect(mapped.get('--disabled-bg'), '--disabled-bg 未接线').toBe('disabledBg')
    expect(mapped.get('--disabled-text'), '--disabled-text 未接线').toBe('disabledText')
  })

  it('style.css 的 :root 声明了 --disabled-bg / --disabled-text', () => {
    const root = rootVars()
    expect(root.get('--disabled-bg'), '默认层缺 --disabled-bg').toBeTruthy()
    expect(root.get('--disabled-text'), '默认层缺 --disabled-text').toBeTruthy()
  })

  it.each(THEME_IDS)('%s 主题：禁用态两个值都非空且互不相同', (id) => {
    const c = THEMES[id].colors
    expect(c.disabledBg, `${id}.disabledBg 为空`).toBeTruthy()
    expect(c.disabledText, `${id}.disabledText 为空`).toBeTruthy()
    expect(c.disabledText, `${id} 禁用文字与底色同值，等于没有禁用态视觉`).not.toBe(c.disabledBg)
  })

  it.each(THEME_IDS)('%s 主题：禁用态文字对比度 ≥3:1（或已登记豁免且未被改低）', (id) => {
    const c = THEMES[id].colors
    // 保留两位再比：豁免表里登记的就是两位小数的实测值，直接用浮点比会因 2.0798 < 2.08 误报
    const ratio = Math.round(contrast(c.disabledText, c.disabledBg) * 100) / 100
    const exempt = DISABLED_CONTRAST_EXEMPT[id]
    if (exempt === undefined) {
      expect(ratio, `${id} 禁用态对比度 ${ratio}:1 < ${DISABLED_MIN_CONTRAST}:1`).toBeGreaterThanOrEqual(
        DISABLED_MIN_CONTRAST,
      )
      return
    }
    // 已登记豁免：只允许持平或变好，改低（哪怕只差 0.01）即红——这是棘轮，不是白名单
    expect(
      ratio,
      `${id} 已登记豁免 ${exempt}:1，实测 ${ratio}:1（被改低了）；修好请从豁免表删除该行`,
    ).toBeGreaterThanOrEqual(exempt)
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
      // 模块一：输入控件高度（与 --btn-height-* 同档但语义独立，防被合并回去）
      '--input-height-lg', '--input-height-md', '--input-height-sm',
      // 模块一：多行输入的最小高度下限（刻意不套 --input-height-*，防被"统一"成固定高度）
      '--input-textarea-min-height',
    ]) {
      expect(css).toContain(`${name}:`)
    }
  })
})
