// web/src/utils/downloadStatus.test.ts
// 下载状态映射与收藏判定的单元测试（唯一事实源的契约）

import { describe, expect, it } from 'vitest'
import {
  DOWNLOAD_STATUS_LABEL_KEYS,
  DOWNLOAD_STATUS_SEVERITY,
  PENDING_QUEUE_LABEL_KEY,
  downloadStatusLabel,
  downloadStatusLabelKey,
  downloadStatusSeverity,
  downloadTooltip,
  isFavorited,
  truncateError,
} from './downloadStatus'

const t = (key: string) => `[${key}]`

describe('downloadStatus 枚举映射', () => {
  it('数据库 6 值全部有 i18n 键与颜色分级', () => {
    const values = ['pending', 'downloading', 'archiving', 'done', 'failed', 'abandoned'] as const
    for (const v of values) {
      expect(DOWNLOAD_STATUS_LABEL_KEYS[v], `${v} 缺 i18n 键`).toBeTruthy()
      expect(DOWNLOAD_STATUS_SEVERITY[v], `${v} 缺颜色分级`).toBeTruthy()
    }
    expect(Object.keys(DOWNLOAD_STATUS_LABEL_KEYS)).toHaveLength(6)
  })

  it('颜色分级符合约定：完成绿 / 进行中蓝 / 待处理灰 / 失败橙 / 放弃红', () => {
    expect(downloadStatusSeverity('done')).toBe('success')
    expect(downloadStatusSeverity('downloading')).toBe('info')
    expect(downloadStatusSeverity('archiving')).toBe('info')
    expect(downloadStatusSeverity('pending')).toBe('secondary')
    expect(downloadStatusSeverity('failed')).toBe('warn')
    expect(downloadStatusSeverity('abandoned')).toBe('danger')
  })

  it('download_status 为 null（收藏但未入队）→ 第 7 项"待下载"兜底，不空白', () => {
    expect(downloadStatusLabelKey(null)).toBe(PENDING_QUEUE_LABEL_KEY)
    expect(downloadStatusLabelKey(undefined)).toBe(PENDING_QUEUE_LABEL_KEY)
    expect(downloadStatusLabel(null, t)).toBe(`[${PENDING_QUEUE_LABEL_KEY}]`)
    expect(downloadStatusSeverity(null)).toBe('secondary')
  })

  it('未知枚举值不空白：回退显示原文 + 灰色', () => {
    expect(downloadStatusLabelKey('some_new_status')).toBe('')
    expect(downloadStatusLabel('some_new_status', t)).toBe('some_new_status')
    expect(downloadStatusSeverity('some_new_status')).toBe('secondary')
  })
})

describe('isFavorited —— 只看后端是否返回收藏对象', () => {
  it('返回对象即视为已收藏（无论下载状态）', () => {
    expect(isFavorited({ favorite_id: 1, status: 'pending', download_status: 'done' })).toBe(true)
  })

  it('下载失败/放弃仍然是有效收藏（旧实现按枚举判定会误判为未收藏）', () => {
    for (const s of ['failed', 'abandoned']) {
      expect(isFavorited({ favorite_id: 1, status: 'pending', download_status: s })).toBe(true)
    }
  })

  it('收藏对象存在但 download_status 为 null（未入队）仍算已收藏', () => {
    expect(isFavorited({ favorite_id: 1, status: 'pending', download_status: null })).toBe(true)
  })

  it('null / undefined（未收藏或他人不可见）视为未收藏', () => {
    expect(isFavorited(null)).toBe(false)
    expect(isFavorited(undefined)).toBe(false)
  })
})

describe('错误文本与悬停提示', () => {
  it('展示截断到 120 字符并加省略号，全量由 title 承载', () => {
    const long = 'x'.repeat(200)
    const out = truncateError(long)
    expect(out).toHaveLength(121)
    expect(out.endsWith('…')).toBe(true)
    expect(truncateError('短错误')).toBe('短错误')
    expect(truncateError(null)).toBe('')
  })

  it('悬停提示含最后尝试时间与全量错误', () => {
    const tip = downloadTooltip({ last_attempt: '2026-03-01', download_error: '采标标准，版权受限' }, t)
    expect(tip).toContain('2026-03-01')
    expect(tip).toContain('采标标准，版权受限')
    expect(downloadTooltip({}, t)).toBe('')
  })
})
