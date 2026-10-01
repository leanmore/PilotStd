// web/src/utils/stdStatus.test.ts
// 状态键工具单测（#32-C / R14-4c）：前端只比较英文键，未知键必须安全兜底。
import { describe, expect, it } from 'vitest'

import {
  ABOLISHED_STATUS_KEYS,
  STD_STATUS_FALLBACK_SEVERITY,
  STD_STATUS_FILTER,
  STD_STATUS_SEVERITY,
  isAbolishedStatusKey,
  isActiveStatusKey,
  severityOfStatusKey,
} from './stdStatus'

describe('stdStatus', () => {
  it('8 个英文状态键都有颜色分级，且废止族统一为 danger', () => {
    expect(Object.keys(STD_STATUS_SEVERITY).sort()).toEqual(
      ['active', 'expired', 'pending', 'superseded', 'unknown', 'upcoming', 'voided', 'withdrawn'].sort(),
    )
    expect(STD_STATUS_SEVERITY.active).toBe('success')
    expect(STD_STATUS_SEVERITY.pending).toBe('warn')
    for (const key of ABOLISHED_STATUS_KEYS) expect(STD_STATUS_SEVERITY[key]).toBe('danger')
  })

  it('severityOfStatusKey：已知键取映射，未知/空值走兜底（默认灰，可覆盖）', () => {
    expect(severityOfStatusKey('active')).toBe('success')
    expect(severityOfStatusKey('withdrawn')).toBe('danger')
    expect(severityOfStatusKey('not-a-key')).toBe(STD_STATUS_FALLBACK_SEVERITY)
    expect(severityOfStatusKey(undefined)).toBe(STD_STATUS_FALLBACK_SEVERITY)
    expect(severityOfStatusKey(null)).toBe(STD_STATUS_FALLBACK_SEVERITY)
    // 视图可传各自改造前的兜底色（PendingView 用 info）
    expect(severityOfStatusKey(undefined, 'info')).toBe('info')
  })

  it('isActiveStatusKey / isAbolishedStatusKey 只认英文键（不认中文文案）', () => {
    expect(isActiveStatusKey('active')).toBe(true)
    expect(isActiveStatusKey('现行')).toBe(false)
    expect(isActiveStatusKey(undefined)).toBe(false)
    expect(isAbolishedStatusKey('withdrawn')).toBe(true)
    expect(isAbolishedStatusKey('expired')).toBe(true)
    expect(isAbolishedStatusKey('active')).toBe(false)
    expect(isAbolishedStatusKey('废止')).toBe(false)
  })

  it('筛选下拉提交英文键（后端兼容历史中文值）', () => {
    expect(STD_STATUS_FILTER).toEqual({ current: 'active', abolished: 'withdrawn', unknown: 'unknown' })
  })
})
