/**
 * `config/index.ts` 的补测（NEW-44，2026-11-24）。
 *
 * `SUPERUSER_USERNAME` 是 **G-028 唯一允许的 admin 字面量定义点**：
 * 只允许 `null` 兜底，**禁止任何字符串默认值**（防止把 admin 账号写死进前端）。
 */

import { describe, expect, it, vi } from 'vitest'

describe('SUPERUSER_USERNAME 环境变量读取', () => {
  it('设置时取该值', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_SUPERUSER_USERNAME', 'test-super')
    const { SUPERUSER_USERNAME } = await import('@/config/index')
    expect(SUPERUSER_USERNAME).toBe('test-super')
    vi.unstubAllEnvs()
  })

  it('未设置时不得出现字符串默认值（G-028）', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_SUPERUSER_USERNAME', '')
    const { SUPERUSER_USERNAME } = await import('@/config/index')
    // 关键契约：不能是 'admin' / 'superadmin' 等写死的账号
    expect(SUPERUSER_USERNAME).not.toBe('admin')
    expect(SUPERUSER_USERNAME).not.toBe('superadmin')
    // 允许 null 或空串
    expect(SUPERUSER_USERNAME === null || SUPERUSER_USERNAME === '').toBe(true)
    vi.unstubAllEnvs()
  })

  it('缺失时不是 undefined（保持可空契约）', async () => {
    vi.resetModules()
    vi.stubEnv('VITE_SUPERUSER_USERNAME', '')
    const { SUPERUSER_USERNAME } = await import('@/config/index')
    expect(SUPERUSER_USERNAME).not.toBeUndefined()
    vi.unstubAllEnvs()
  })
})
