// web/src/utils/taskPipeline.test.ts — 追加：批次10（P1-7.1 B-13）year 缺省不丢件
// 背景：`TaskView.vue` 规范化步骤曾用 `f.logical_code && f.number && f.year` 的真值门，
// 把后端 B 通道合法产物 `year=0`（API STD 610 / ASME B16.5 / BPVC 无年份）打回前端正则 → null
// → 该件不进入 normalizeResults → buildArchiveItems 的 archiveMap 缺键 → 文件不归档（静默丢失）。
import { describe, expect, it } from 'vitest'

import { resolveScanFields } from './taskPipeline'

describe('resolveScanFields 后端已解析字段优先、year 缺省不丢件', () => {
  it('year=0 是后端合法产物：直接透传，不回退前端正则、不丢件', () => {
    const row = resolveScanFields({
      full_path: 'C:/in/API STD 610.pdf',
      standard_number: 'API STD 610',
      logical_code: 'API',
      number: 610,
      year: 0,
    })
    expect(row).toEqual({ logical_code: 'API', number: 610, year: 0 })
  })

  it('year 字段缺失（undefined）同样按 year=0 处理，不丢件', () => {
    const row = resolveScanFields({
      full_path: 'C:/in/ASME B16.5.pdf',
      standard_number: 'ASME B16.5',
      logical_code: 'ASME',
      number: 16,
    })
    expect(row).toEqual({ logical_code: 'ASME', number: 16, year: 0 })
  })

  it('后端字段缺失时才回落前端正则', () => {
    const row = resolveScanFields({
      full_path: 'C:/in/GB_T 1-2020.pdf',
      standard_number: 'GB/T 1-2020',
      logical_code: '',
      number: 0,
      year: 0,
    })
    expect(row).toEqual({ logical_code: 'GB/T', number: 1, year: 2020 })
  })

  it('两条路径都无法解析时返回 null（由调用方 warn 后跳过）', () => {
    expect(resolveScanFields({ standard_number: '不可解析' })).toBeNull()
    expect(resolveScanFields({})).toBeNull()
  })
})
