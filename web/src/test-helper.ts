// Node.js 原生测试 helper — 提供与 Vitest 兼容的 expect / vi / describe / it
// 使用方式: import { describe, it, expect, vi, beforeEach } from '../test-helper.js'

import assert from 'node:assert'
import { mock } from 'node:test'

// ── expect() 兼容层 ──

export function expect(actual: unknown) {
  return {
    toBe(expected: unknown) { assert.strictEqual(actual, expected) },
    toEqual(expected: unknown) { assert.deepStrictEqual(actual, expected) },
    toBeTruthy() { assert.ok(actual) },
    toBeFalsy() { assert.ok(!actual) },
    toBeGreaterThan(expected: number) { assert.ok((actual as number) > expected, `expected ${actual} > ${expected}`) },
    toBeGreaterThanOrEqual(expected: number) { assert.ok((actual as number) >= expected) },
    toBeLessThan(expected: number) { assert.ok((actual as number) < expected) },
    toBeLessThanOrEqual(expected: number) { assert.ok((actual as number) <= expected) },
    toContain(expected: unknown) { assert.ok((actual as any[]).includes(expected), `expected ${JSON.stringify(actual)} to contain ${expected}`) },
    toHaveLength(expected: number) { assert.strictEqual((actual as any[]).length, expected) },
    toBeInstanceOf(expected: any) { assert.ok(actual instanceof expected) },
    toMatch(expected: RegExp) { assert.ok(expected.test(actual as string)) },
    toBeDefined() { assert.ok(actual !== undefined) },
    toBeNull() { assert.strictEqual(actual, null) },
    // 非对称匹配器
    resolves: {
      toEqual: async (expected: unknown) => {
        assert.deepStrictEqual(await (actual as Promise<unknown>), expected)
      },
      toBe: async (expected: unknown) => {
        assert.strictEqual(await (actual as Promise<unknown>), expected)
      },
    },
    rejects: {
      toThrow: async () => {
        await assert.rejects(actual as Promise<unknown>)
      },
    },
  }
}

// ── vi 兼容层 ──

type MockFn<T extends (...args: any[]) => any> = T & {
  calls: Parameters<T>[]
  mockImplementation: (impl: T) => MockFn<T>
}

export const vi = {
  fn: <T extends (...args: any[]) => any>(impl?: T): MockFn<T> => {
    const fn = ((...args: Parameters<T>) => {
      (fn as any).calls.push(args)
      if (impl) return impl(...args)
      return undefined
    }) as MockFn<T>
    ;(fn as any).calls = [] as Parameters<T>[]
    fn.mockImplementation = (newImpl: T) => vi.fn(newImpl) as MockFn<T>
    return fn
  },
  mock(path: string, factory?: () => any) {
    if (factory) {
      const result = factory()
      // 使用 node:test mock.module 拦截 ESM 导入
      // 注意：必须在模块被导入前调用，测试文件中需使用动态 import
      const namedExports: Record<string, any> = {}
      for (const [key, value] of Object.entries(result)) {
        namedExports[key] = value
      }
      mock.module(path, { namedExports })
    }
  },
  clearAllMocks() {},
  resetAllMocks() {},
  spyOn(obj: any, method: string) {
    const original = obj[method]
    const spy = vi.fn(original)
    obj[method] = spy
    return spy
  },
}

// ── 从 node:test 重新导出 ──

export { describe, it, beforeEach, afterEach, before, after } from 'node:test'
