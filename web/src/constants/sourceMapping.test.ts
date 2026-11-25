// web/src/constants/sourceMapping.test.ts
// sourceMapping.ts 是纯映射表（没有函数），未知来源的兜底在调用方：
//   AnnounceView.vue：SOURCE_TO_URL[source_site] || 'unknown'（拼公告详情路由）
//   LegacyRedirect.vue：SOURCE_TO_URL[item.source_site] || item.source_site（保持原值）
// 本测试锁定 DB 值（announcement_*）↔ URL 标识（annc_*）的双向映射与调用方兜底。
import { describe, expect, it } from 'vitest'

import { SOURCE_TO_URL, URL_TO_SOURCE } from './sourceMapping'

const EXPECTED_SOURCE_TO_URL: Record<string, string> = {
  announcement_gb: 'annc_gb',
  announcement_hb: 'annc_hb',
  announcement_db: 'annc_db',
}

describe('sourceMapping 来源站点 ↔ URL 标识双向映射', () => {
  it('SOURCE_TO_URL 覆盖国标 / 行标 / 地标三类公告源，且无多余键', () => {
    expect(SOURCE_TO_URL).toEqual(EXPECTED_SOURCE_TO_URL)
  })

  it('URL_TO_SOURCE 是 SOURCE_TO_URL 的精确反向表', () => {
    const expectedReverse = Object.fromEntries(
      Object.entries(EXPECTED_SOURCE_TO_URL).map(([source, url]) => [url, source]),
    )
    expect(URL_TO_SOURCE).toEqual(expectedReverse)
  })

  it('双向 round-trip 恒等（列表 source_site ↔ 详情页 URL 段）', () => {
    for (const [source, url] of Object.entries(EXPECTED_SOURCE_TO_URL)) {
      expect(SOURCE_TO_URL[source]).toBe(url)
      expect(URL_TO_SOURCE[url]).toBe(source)
    }
  })

  it('命名约定：DB 值以 announcement_ 开头，URL 标识以 annc_ 开头', () => {
    for (const source of Object.keys(SOURCE_TO_URL)) expect(source.startsWith('announcement_')).toBe(true)
    for (const url of Object.values(SOURCE_TO_URL)) expect(url.startsWith('annc_')).toBe(true)
    for (const url of Object.keys(URL_TO_SOURCE)) expect(url.startsWith('annc_')).toBe(true)
  })

  it('未知来源查表返回 undefined（不抛错、不落到错误映射）', () => {
    expect(SOURCE_TO_URL['announcement_unknown']).toBeUndefined()
    expect(URL_TO_SOURCE['annc_unknown']).toBeUndefined()
    expect(SOURCE_TO_URL['']).toBeUndefined()
    expect(URL_TO_SOURCE['']).toBeUndefined()
  })

  it('调用方兜底：未知来源落 unknown 路由 / 保持原始 source_site', () => {
    const sourceSite = 'announcement_unknown'
    expect(SOURCE_TO_URL[sourceSite] || 'unknown').toBe('unknown')
    expect(SOURCE_TO_URL[sourceSite] || sourceSite).toBe(sourceSite)
  })
})
