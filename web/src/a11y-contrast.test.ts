/**
 * 按钮配色对比度契约（2026-11-20，对应 27 日志 #87 / 总表 G-15）。
 *
 * 背景：深色主题下 32 个按钮低于 WCAG AA，最严重的是 outlined danger（1.36:1，两段红同亮度）。
 * 本文件用**主题令牌的真实取值**算对比度，锁住三个决定：
 *   1. outlined danger 的文字必须用 --danger-text（不是 --danger 实心底上的白字/同色字）；
 *   2. 悬浮工作台按钮用 --primary-hover 打底，白字才够；
 *   3. 侧栏“收起”用 --text-bright，13px 小字才过 4.5。
 * 谁把令牌改回去，这里会红。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { THEMES } from './config/themes'

function srgb(v: number): number {
  const c = v / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function luminance(hex: string): number {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)
}

export function contrast(a: string, b: string): number {
  const l1 = luminance(a)
  const l2 = luminance(b)
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
}

const MODES = ['light', 'dark'] as const
const SMALL_TEXT = 4.5

describe.each(MODES)('按钮配色对比度（%s 主题）', (mode) => {
  const t = THEMES[mode].colors

  it('outlined danger 文字在页面底色上 ≥ 4.5:1', () => {
    // 描边样式是透明底，文字直接压在 --bg 上
    expect(contrast(t.dangerText, t.bg)).toBeGreaterThanOrEqual(SMALL_TEXT)
  })

  it('悬浮工作台按钮：白字 on --primary-hover ≥ 3:1（图标按钮，文字在 aria-label）', () => {
    // 可视内容是图标 ⇒ 适用 WCAG 1.4.11 非文本对比度 3:1；不带 sr-only 文本
    expect(contrast('#ffffff', t.primaryHover)).toBeGreaterThanOrEqual(3)
  })

  it('侧栏“收起”：--text-bright on --surface ≥ 4.5:1', () => {
    expect(contrast(t.textBright, t.surface)).toBeGreaterThanOrEqual(SMALL_TEXT)
  })
})

describe('CSS 落地（防规则被删）', () => {
  it('style.css 含 outlined danger 的透明底规则', () => {
    const css = readFileSync(resolve(__dirname, 'style.css'), 'utf8')
    const idx = css.indexOf('.p-button-danger.p-button-outlined')
    expect(idx).toBeGreaterThan(-1)
    const block = css.slice(idx, idx + 240)
    expect(block).toContain('background: transparent')
    expect(block).toContain('var(--danger-text)')
  })
})

/**
 * A-50 回归：--warning 作为文字（LogBar 日志行，背景是 --bg）要 ≥4.5:1；
 * 作为状态圆点（NotificationBell）属非文本 UI，≥3:1（被 4.5 覆盖）。
 * 改回 #f59e0b 会在这里红（light 1.96 / green 1.91）。
 */
describe('状态色 --warning 可读性（四主题）', () => {
  for (const id of ['light', 'dark', 'green', 'blue']) {
    it(`${id} 主题：warning on bg ≥ 4.5:1`, () => {
      expect(contrast(THEMES[id].colors.warning, THEMES[id].colors.bg)).toBeGreaterThanOrEqual(4.5)
    })
  }
})
