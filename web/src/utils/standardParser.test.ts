// web/src/utils/standardParser.test.ts
// 标准号回落解析（仅当 scan 结果缺 logical_code/number/year 时使用）契约测试。
//
// 覆盖：国标 / 行标 / 地标 / 团标、年份分隔符（全角破折号 — / ASCII 连字符 - / 冒号 :）、
//       非法输入统一返回 null（不抛错），以及当前实现的两处已知边界：
//       · 前缀与数字之间无空格时贪婪匹配会吞掉数字（'GB/T19001—2020' 解析错位）；
//       · 号码带小数位时 parseInt 截断成整数。
// 这些边界是先探针实测后锁定的现状，若产品决定修正解析器，需同步更新本文件。
import { describe, expect, it } from 'vitest'

import { parseStandardNumber } from './standardParser'

const GB_T_19001_2020 = { logical_code: 'GB/T', number: 19001, year: 2020 }

describe('parseStandardNumber 合法标准号', () => {
  it('国标 GB/T + 全角破折号（中文标准常用写法）', () => {
    expect(parseStandardNumber('GB/T 19001—2020')).toEqual(GB_T_19001_2020)
  })

  it('三种年份分隔符等价：— / - / :', () => {
    expect(parseStandardNumber('GB/T 19001—2020')).toEqual(GB_T_19001_2020)
    expect(parseStandardNumber('GB/T 19001-2020')).toEqual(GB_T_19001_2020)
    expect(parseStandardNumber('GB/T 19001:2020')).toEqual(GB_T_19001_2020)
  })

  it('行标 JB/T、地标 DB31/T、团标 T/CECS 都能拆出逻辑前缀', () => {
    expect(parseStandardNumber('JB/T 1234—2019')).toEqual({ logical_code: 'JB/T', number: 1234, year: 2019 })
    expect(parseStandardNumber('DB31/T 123—2022')).toEqual({ logical_code: 'DB31/T', number: 123, year: 2022 })
    expect(parseStandardNumber('T/CECS 123—2020')).toEqual({ logical_code: 'T/CECS', number: 123, year: 2020 })
  })

  it('国际标准 ISO 9001:2015', () => {
    expect(parseStandardNumber('ISO 9001:2015')).toEqual({ logical_code: 'ISO', number: 9001, year: 2015 })
  })

  it('前缀与数字间多个空格、分隔符两侧带空格都能解析', () => {
    expect(parseStandardNumber('GB/T  19001—2020')).toEqual(GB_T_19001_2020)
    expect(parseStandardNumber('GB/T 19001 — 2020')).toEqual(GB_T_19001_2020)
  })
})

describe('parseStandardNumber 非法 / 不支持输入的兜底', () => {
  it('空值（空串 / null / undefined）返回 null', () => {
    expect(parseStandardNumber('')).toBeNull()
    expect(parseStandardNumber(null as unknown as string)).toBeNull()
    expect(parseStandardNumber(undefined as unknown as string)).toBeNull()
  })

  it('不带年份返回 null（本回落方案只解析带 4 位年份的完整标准号）', () => {
    expect(parseStandardNumber('GB/T 19001')).toBeNull()
    expect(parseStandardNumber('ISO 9001')).toBeNull()
  })

  it('年份不是 4 位数字返回 null（2 位 / 5 位）', () => {
    expect(parseStandardNumber('GB/T 19001—20')).toBeNull()
    expect(parseStandardNumber('GB/T 19001—20200')).toBeNull()
  })

  it('带余缀、多段年份、尾随空格/换行、前后空格都返回 null（正则是整串锚定）', () => {
    expect(parseStandardNumber('GB/T 19001—2020 年')).toBeNull()
    expect(parseStandardNumber('GB/T 19001—2020—2021')).toBeNull()
    expect(parseStandardNumber('GB/T 19001—2020 ')).toBeNull()
    expect(parseStandardNumber('  GB/T 19001—2020')).toBeNull()
    expect(parseStandardNumber('GB/T 19001—2020\n')).toBeNull()
  })

  it('小写、非标准文本返回 null', () => {
    expect(parseStandardNumber('gb/t 19001—2020')).toBeNull()
    expect(parseStandardNumber('关于征求国家标准意见的通知')).toBeNull()
  })

  it('全角字母 / 全角数字 / 全角连字符（－）/ 全角冒号（：）不识别，返回 null', () => {
    // 注意：全角破折号「—」(U+2014) 是支持的，见合法输入用例；这里锁定的是其余全角形式不支持。
    expect(parseStandardNumber('ＧＢ/T 19001—2020')).toBeNull()
    expect(parseStandardNumber('GB/T １９００１—２０２０')).toBeNull()
    expect(parseStandardNumber('GB/T 19001－2020')).toBeNull()
    expect(parseStandardNumber('GB/T 19001：2020')).toBeNull()
  })

  it('其它连字符（en dash – / 双连字符）不识别', () => {
    expect(parseStandardNumber('GB/T 19001–2020')).toBeNull()
    expect(parseStandardNumber('GB/T 19001--2020')).toBeNull()
  })
})

describe('parseStandardNumber 当前实现边界（探针实测，非产品承诺）', () => {
  it('前缀与数字间无空格时贪婪匹配吞掉数字：GB/T19001—2020 → 前缀 GB/T1900 + 号码 1', () => {
    // 成因：^([A-Z][A-Z0-9/]+)\s*(\d+...) 中 \s* 允许 0 空格，贪婪字符类会吃掉数字再回退 1 位。
    expect(parseStandardNumber('GB/T19001—2020')).toEqual({
      logical_code: 'GB/T1900',
      number: 1,
      year: 2020,
    })
  })

  it('号码部分按 parseInt 归一：小数位截断、前导零丢弃、年份前导零同样归一', () => {
    expect(parseStandardNumber('GB/T 19001.5—2020')).toEqual(GB_T_19001_2020)
    expect(parseStandardNumber('GB/T 00019001—2020')).toEqual(GB_T_19001_2020)
    expect(parseStandardNumber('GB/T 19001—0202')).toEqual({ logical_code: 'GB/T', number: 19001, year: 202 })
  })
})
