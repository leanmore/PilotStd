/**
 * 四主题配色契约（2026-11-20 统一规范 v2）。
 *
 * 统一口径（四个主题必须一致，不是各调各的）：
 * 1. `--primary` 只做**强调文字/图标/描边**：对 surface ≥ 4.5:1；
 * 2. `--primary-fill` 只做**主按钮/选中态底色**：白字 ≥ 4.5:1，hover 恒比 fill 更深；
 *    两者拆开是因为同一 token 无法同时满足“深底浅字”和“浅底白字”。
 * 3. 文字梯度 heading ≥ bright ≥ text ≥ secondary ≥ dim，分别 ≥ 12 / 9 / 7 / 4.5 / 4.5（dim 对 raised）；
 * 4. 语义色（success/danger/warning/info）的 `-text` 对 surface ≥ 4.5:1；
 * 5. 背景透明度同族一致：primaryBg 0.08~0.16、语义 bg 0.10~0.18、描边 0.28~0.40；
 * 6. 边框必须与 surface 可分辨（对比 ≥ 1.15:1）。
 */
import { describe, expect, it } from 'vitest'
import { THEMES } from './themes'

function srgb(v: number): number {
  const c = v / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function lum(hex: string): number {
  const h = hex.replace('#', '')
  return 0.2126 * srgb(parseInt(h.slice(0, 2), 16)) +
    0.7152 * srgb(parseInt(h.slice(2, 4), 16)) +
    0.0722 * srgb(parseInt(h.slice(4, 6), 16))
}

export function contrast(a: string, b: string): number {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}

function alpha(rgba: string): number {
  const m = rgba.match(/rgba?\([^)]*,\s*([0-9.]+)\s*\)/)
  return m ? parseFloat(m[1]) : 1
}

const ids = Object.keys(THEMES)

describe.each(ids)('主题 %s 的配色契约', (id) => {
  const t = THEMES[id].colors

  it('primary 作为强调文字对 surface ≥ 4.5:1', () => {
    expect(contrast(t.primary, t.surface)).toBeGreaterThanOrEqual(4.5)
  })

  it('primary-fill 上白字 ≥ 4.5:1（四主题统一）', () => {
    expect(contrast('#ffffff', t.primaryFill)).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#ffffff', t.primaryFillHover)).toBeGreaterThanOrEqual(4.5)
  })

  it('hover 恒比 fill 更深（方向统一）', () => {
    expect(lum(t.primaryFillHover)).toBeLessThan(lum(t.primaryFill))
  })

  it('文字梯度 heading ≥ bright ≥ text ≥ secondary ≥ dim', () => {
    expect(contrast(t.textHeading, t.surface)).toBeGreaterThanOrEqual(12)
    expect(contrast(t.textBright, t.surface)).toBeGreaterThanOrEqual(9)
    expect(contrast(t.text, t.surface)).toBeGreaterThanOrEqual(7)
    expect(contrast(t.textSecondary, t.surface)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(t.textDim, t.surfaceRaised)).toBeGreaterThanOrEqual(4.5)
  })

  it('语义 -text 对 surface ≥ 4.5:1', () => {
    for (const key of ['successText', 'dangerText', 'warnText', 'infoText'] as const) {
      expect(contrast(t[key], t.surface), key).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('背景透明度符合统一区间', () => {
    expect(alpha(t.primaryBg)).toBeGreaterThanOrEqual(0.08)
    expect(alpha(t.primaryBg)).toBeLessThanOrEqual(0.16)
    for (const key of ['successBg', 'dangerBg', 'warningBg', 'infoBg'] as const) {
      expect(alpha(t[key]), key).toBeGreaterThanOrEqual(0.1)
      expect(alpha(t[key]), key).toBeLessThanOrEqual(0.18)
    }
    expect(alpha(t.primaryBorder)).toBeGreaterThanOrEqual(0.28)
    expect(alpha(t.primaryBorder)).toBeLessThanOrEqual(0.4)
  })

  it('边框与 surface 可分辨（≥1.15:1）', () => {
    expect(contrast(t.border, t.surface)).toBeGreaterThanOrEqual(1.15)
  })
})

describe('四主题族内一致', () => {
  const lightFamily = ['light', 'green']
  const darkFamily = ['dark', 'blue']

  it('同族主题使用同一套透明度', () => {
    for (const family of [lightFamily, darkFamily]) {
      const sig = family.map((id) => {
        const c = THEMES[id].colors
        return [c.primaryBg, c.successBg, c.dangerBg, c.warningBg, c.infoBg, c.primaryBorder]
          .map((v) => alpha(v))
          .join('|')
      })
      expect(new Set(sig).size, family.join(',')).toBe(1)
    }
  })

  it('同一语义 token 在四个主题里语义一致：danger 的 bg 从 danger 派生', () => {
    for (const id of ids) {
      const c = THEMES[id].colors
      // rgba(R,G,B,α) 的 RGB 必须与对应基色一致，避免“红色底配绿色系”的错配
      const rgb = c.dangerBg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
      expect(rgb).not.toBeNull()
      expect(`#${[1, 2, 3].map((i) => parseInt(rgb![i], 10).toString(16).padStart(2, '0')).join('')}`)
        .toBe(c.danger.toLowerCase())
    }
  })
})
