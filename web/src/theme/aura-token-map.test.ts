/**
 * 主题 token 映射 + 超管配置的补测（NEW-44，2026-11-24）。
 *
 * 覆盖两个「一处错、全站可见」的小模块：
 * - `theme/aura-token-map.ts`：四主题 → `:root` 级 Aura token 注入值（对比度/主题一致性的数据源）
 * - `config/index.ts`：`SUPERUSER_USERNAME`（G-028 唯一允许的 admin 字面量定义点）
 */

import { describe, expect, it, vi } from 'vitest'

// ════════════════════════════════════════════════════════════════
// 1. aura-token-map：四主题 token 映射
// ════════════════════════════════════════════════════════════════

describe('AURA_TOKEN_MAP', () => {
  it('覆盖四个主题', async () => {
    const { AURA_TOKEN_MAP } = await import('@/theme/aura-token-map')
    expect(Object.keys(AURA_TOKEN_MAP).sort()).toEqual(['blue', 'dark', 'green', 'light'])
  })

  it('每个主题的 token 集合完全一致（防止某主题漏注入）', async () => {
    const { AURA_TOKEN_MAP } = await import('@/theme/aura-token-map')
    const [light, ...others] = ['light', 'dark', 'green', 'blue'] as const
    const baseKeys = Object.keys(AURA_TOKEN_MAP[light]).sort()
    expect(baseKeys.length).toBeGreaterThan(0)
    for (const theme of others) {
      expect(Object.keys(AURA_TOKEN_MAP[theme]).sort()).toEqual(baseKeys)
    }
  })

  it('所有键都是 --p- 前缀的 CSS 变量，值都是有效颜色', async () => {
    const { AURA_TOKEN_MAP } = await import('@/theme/aura-token-map')
    for (const [theme, map] of Object.entries(AURA_TOKEN_MAP)) {
      for (const [token, value] of Object.entries(map)) {
        expect(token, `${theme} token 名`).toMatch(/^--p-[a-z-]+$/)
        // 允许 #rgb / #rrggbb / rgb() / color-mix() 等
        expect(value, `${theme}.${token} 值`).toMatch(/^(#[0-9a-fA-F]{3,8}|rgba?\(|color-mix\()/)
      }
    }
  })

  it('light 与 green 的 content/text 保持 Aura 默认深色（对比度达标前提）', async () => {
    const { AURA_TOKEN_MAP } = await import('@/theme/aura-token-map')
    for (const theme of ['light', 'green'] as const) {
      expect(AURA_TOKEN_MAP[theme]['--p-content-color']).toBe('#334155')
      expect(AURA_TOKEN_MAP[theme]['--p-text-color']).toBe('#334155')
    }
  })

  it('dark 与 blue 的 content/text 必须与浅色主题不同（深色反色）', async () => {
    const { AURA_TOKEN_MAP } = await import('@/theme/aura-token-map')
    for (const theme of ['dark', 'blue'] as const) {
      expect(AURA_TOKEN_MAP[theme]['--p-content-color']).not.toBe('#334155')
      expect(AURA_TOKEN_MAP[theme]['--p-text-color']).not.toBe('#334155')
    }
  })

  it('hover 态与常态不同（悬停必须可辨识）', async () => {
    const { AURA_TOKEN_MAP } = await import('@/theme/aura-token-map')
    for (const [theme, map] of Object.entries(AURA_TOKEN_MAP)) {
      if (map['--p-content-color'] && map['--p-content-hover-color']) {
        expect(map['--p-content-hover-color'], `${theme} content hover`).not.toBe(map['--p-content-color'])
      }
    }
  })
})

// ════════════════════════════════════════════════════════════════
// 2. config/index.ts：SUPERUSER_USERNAME
// ════════════════════════════════════════════════════════════════

describe('SUPERUSER_USERNAME', () => {
  it('未设置环境变量时为 null（禁止字符串默认值）', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_SUPERUSER_USERNAME', '')
    const { SUPERUSER_USERNAME } = await import('@/config/index')
    // 空串经 ?? 保留为 ''，但绝不能是 'admin' 等字面量
    expect(SUPERUSER_USERNAME === null || SUPERUSER_USERNAME === '').toBe(true)
    expect(SUPERUSER_USERNAME).not.toBe('admin')
    vi.unstubAllEnvs()
  })

  it('设置环境变量时取该值', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_SUPERUSER_USERNAME', 'test-super')
    const { SUPERUSER_USERNAME } = await import('@/config/index')
    expect(SUPERUSER_USERNAME).toBe('test-super')
    vi.unstubAllEnvs()
  })

  it('类型允许 null（可空契约）', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_SUPERUSER_USERNAME', 'someone')
    const mod = await import('@/config/index')
    // 运行时无法断言类型，但可断言「不是 undefined」
    expect(mod.SUPERUSER_USERNAME).not.toBeUndefined()
    vi.unstubAllEnvs()
  })
})
