import { describe, it, expect } from 'vitest'
import {
  ANNOUNCE_PAGE_SIZES,
  TASK_HISTORY_PAGE_SIZES,
  resolveRows,
} from './pagination'

describe('pagination', () => {
  it('公告提供 25/50/100，任务历史提供 10/50/100', () => {
    expect(ANNOUNCE_PAGE_SIZES).toEqual([25, 50, 100])
    expect(TASK_HISTORY_PAGE_SIZES).toEqual([10, 50, 100])
  })

  it('合法的 rows 生效，非法/缺失保持当前值', () => {
    expect(resolveRows(100, 25, ANNOUNCE_PAGE_SIZES)).toBe(100)
    expect(resolveRows(50, 10, TASK_HISTORY_PAGE_SIZES)).toBe(50)
    expect(resolveRows(undefined, 25, ANNOUNCE_PAGE_SIZES)).toBe(25)
    expect(resolveRows(30, 25, ANNOUNCE_PAGE_SIZES)).toBe(25)
  })
})
