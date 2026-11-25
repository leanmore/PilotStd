// web/src/utils/taskPipeline.test.ts
// 归档项构建（从 TaskView 抽出，控制组件有效行）契约测试：
//   扫描件 ∩ 归一化结果 → 归档项；下载成功件补充归档（Web 五段式的下载件不能留在 /standards 根目录）；
//   按 source_path 去重；非 success 状态 / 缺字段 / 标准号无法解析 → 跳过（异常分支不抛错、不中断循环）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { buildArchiveItems } from './taskPipeline'

type Row = Record<string, unknown>

function scanFile(overrides: Row = {}): Row {
  return {
    full_path: 'C:/in/a.pdf',
    name: 'a.pdf',
    logical_code: 'GB/T',
    number: 1,
    year: 2020,
    std_name: '标准A',
    num_prefix: 'P',
    ...overrides,
  }
}

function normalizeResult(sourcePath: string, newFilename: string): Row {
  return { source_path: sourcePath, new_filename: newFilename }
}

function downloadResult(overrides: Row = {}): Row {
  return {
    status: 'success',
    saved_path: 'D:/out/GB_T 1-2020.pdf',
    standard_number: 'GB/T 1-2020',
    standard_name: '下载件',
    ...overrides,
  }
}

describe('buildArchiveItems 扫描件 + 归一化结果', () => {
  it('只归档被归一化结果覆盖的扫描件，未归一化的扫描件被过滤掉', () => {
    const items = buildArchiveItems(
      [scanFile({ full_path: 'C:/in/a.pdf' }), scanFile({ full_path: 'C:/in/orphan.pdf', name: 'orphan.pdf' })],
      [normalizeResult('C:/in/a.pdf', 'GB_T 1-2020.pdf')],
      [],
    )

    expect(items).toHaveLength(1)
    expect(items[0].source_path).toBe('C:/in/a.pdf')
    expect(items[0].new_filename).toBe('GB_T 1-2020.pdf')
  })

  it('字段映射与默认值：new_filename 空串回落文件名，缺失字段用空串/0 兜底', () => {
    const items = buildArchiveItems(
      [scanFile({ full_path: 'C:/in/empty.pdf', name: 'empty.pdf', logical_code: undefined, number: undefined, year: undefined, std_name: undefined, num_prefix: undefined })],
      [normalizeResult('C:/in/empty.pdf', '')],
      [],
    )

    expect(items).toEqual([
      {
        source_path: 'C:/in/empty.pdf',
        new_filename: 'empty.pdf',
        logical_code: '',
        number: 0,
        year: 0,
        std_name: 'empty.pdf',
        num_prefix: '',
        ext: 'pdf',
      },
    ])
  })

  it('ext 判断大小写不敏感：.PDF → pdf，其余（.docx）→ doc', () => {
    const items = buildArchiveItems(
      [scanFile({ full_path: 'C:/in/a.PDF', name: 'a.PDF' }), scanFile({ full_path: 'C:/in/b.docx', name: 'b.docx' })],
      [normalizeResult('C:/in/a.PDF', 'a_new.pdf'), normalizeResult('C:/in/b.docx', 'b_new.docx')],
      [],
    )

    expect(items.map((i) => i.ext)).toEqual(['pdf', 'doc'])
  })
})

describe('buildArchiveItems 下载成功件补录', () => {
  it('success 且有 saved_path / standard_number：解析标准号并取路径 basename（Windows 分隔符）', () => {
    const items = buildArchiveItems(
      [],
      [],
      [downloadResult({ saved_path: 'D:\\out\\GB_T 9001-2015.pdf', standard_number: 'GB/T 9001-2015', standard_name: '下载件' })],
    )

    expect(items).toEqual([
      {
        source_path: 'D:\\out\\GB_T 9001-2015.pdf',
        new_filename: 'GB_T 9001-2015.pdf',
        logical_code: 'GB/T',
        number: 9001,
        year: 2015,
        std_name: '下载件',
        num_prefix: '',
        ext: 'pdf',
      },
    ])
  })

  it('Unix 分隔符同样能取 basename；standard_name 为空时用文件名兜底', () => {
    const items = buildArchiveItems(
      [],
      [],
      [downloadResult({ saved_path: 'D:/out/ISO 9001-2015.pdf', standard_number: 'ISO 9001:2015', standard_name: '' })],
    )

    expect(items[0].new_filename).toBe('ISO 9001-2015.pdf')
    expect(items[0].std_name).toBe('ISO 9001-2015.pdf')
    expect(items[0].logical_code).toBe('ISO')
    expect(items[0].year).toBe(2015)
  })

  it('非 success 状态（pending / downloading / failed / skipped）不补录：终态判定只认 success', () => {
    const items = buildArchiveItems(
      [],
      [],
      ['pending', 'downloading', 'failed', 'skipped'].map((status) => downloadResult({ status })),
    )

    expect(items).toEqual([])
  })

  it('缺 saved_path 或 standard_number 的下载件跳过', () => {
    const items = buildArchiveItems(
      [],
      [],
      [
        downloadResult({ saved_path: '' }),
        downloadResult({ saved_path: undefined }),
        downloadResult({ standard_number: '' }),
        downloadResult({ standard_number: undefined }),
      ],
    )

    expect(items).toEqual([])
  })

  it('按 source_path 去重：已归档的扫描路径不再补录，重复 saved_path 只追加一次', () => {
    const items = buildArchiveItems(
      [scanFile({ full_path: 'C:/in/a.pdf' })],
      [normalizeResult('C:/in/a.pdf', 'GB_T 1-2020.pdf')],
      [
        downloadResult({ saved_path: 'C:/in/a.pdf' }),
        downloadResult({ saved_path: 'D:/out/x.pdf', standard_number: 'GB/T 2-2001' }),
        downloadResult({ saved_path: 'D:/out/x.pdf', standard_number: 'GB/T 2-2001' }),
      ],
    )

    expect(items.map((i) => i.source_path)).toEqual(['C:/in/a.pdf', 'D:/out/x.pdf'])
  })
})

describe('buildArchiveItems 异常分支', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    warnSpy.mockRestore()
  })

  it('标准号无法解析：跳过该下载件、console.warn 留痕，并继续处理后续下载件', () => {
    const items = buildArchiveItems(
      [],
      [],
      [
        downloadResult({ saved_path: 'D:/out/noparse.pdf', standard_number: '不可解析' }),
        downloadResult({ saved_path: 'D:/out/ok.pdf', standard_number: 'GB/T 2-2001' }),
      ],
    )

    expect(items).toHaveLength(1)
    expect(items[0].source_path).toBe('D:/out/ok.pdf')
    expect(warnSpy).toHaveBeenCalledTimes(1)
    expect(warnSpy.mock.calls[0]).toEqual([
      '[Archive] 跳过无法解析的下载件:',
      '不可解析',
      'D:/out/noparse.pdf',
    ])
  })

  it('空 / null / undefined 输入安全返回空数组', () => {
    expect(buildArchiveItems([], [], [])).toEqual([])
    expect(buildArchiveItems(null as unknown as unknown[], null as unknown as unknown[], null as unknown as unknown[])).toEqual([])
    expect(buildArchiveItems(undefined as unknown as unknown[], undefined as unknown as unknown[], undefined as unknown as unknown[])).toEqual([])
  })

  it('不修改入参数组（TaskView 会复用同一批扫描 / 下载结果）', () => {
    const scan = [scanFile()]
    const normalize = [normalizeResult('C:/in/a.pdf', 'GB_T 1-2020.pdf')]
    const downloads = [downloadResult({ saved_path: 'D:/out/x.pdf', standard_number: 'GB/T 2-2001' })]

    buildArchiveItems(scan, normalize, downloads)

    expect(scan).toHaveLength(1)
    expect(Object.keys(scan[0])).toEqual(['full_path', 'name', 'logical_code', 'number', 'year', 'std_name', 'num_prefix'])
    expect(normalize).toHaveLength(1)
    expect(downloads).toHaveLength(1)
  })
})

describe('buildArchiveItems 优先消费后端解析字段（P1-C1，2026-11-24）', () => {
  it('后端给出 API/ASME 解析字段时，不再因前端正则不识别而跳过归档', () => {
    // 前端正则对 \API STD 610\ 是解析不出的（38/40 全盲）；后端 parse_std_number 已能给出字段。
    const items = buildArchiveItems(
      [],
      [],
      [
        downloadResult({
          saved_path: 'D:/out/API STD 610.pdf',
          standard_number: 'API STD 610',
          logical_code: 'API',
          number: 610,
          year: 0,
          num_prefix: 'STD',
        }),
        downloadResult({
          saved_path: 'D:/out/ASME B16.5-2020.pdf',
          standard_number: 'ASME B16.5-2020',
          logical_code: 'ASME',
          number: 16,
          year: 2020,
          num_prefix: 'B',
        }),
      ],
    )

    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({ logical_code: 'API', number: 610, num_prefix: 'STD' })
    expect(items[1]).toMatchObject({ logical_code: 'ASME', number: 16, year: 2020, num_prefix: 'B' })
  })

  it('后端字段缺失（旧接口/解析失败）时回落前端正则解析', () => {
    const items = buildArchiveItems(
      [],
      [],
      [downloadResult({ saved_path: 'D:/out/GB_T 1-2020.pdf', standard_number: 'GB/T 1-2020' })],
    )

    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ logical_code: 'GB/T', number: 1, year: 2020 })
  })

  it('后端字段为空串 / number=0 视为缺失，仍回落前端解析', () => {
    const items = buildArchiveItems(
      [],
      [],
      [
        downloadResult({
          saved_path: 'D:/out/GB_T 2-2001.pdf',
          standard_number: 'GB/T 2-2001',
          logical_code: '',
          number: 0,
        }),
      ],
    )

    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ logical_code: 'GB/T', number: 2, year: 2001 })
  })
})
