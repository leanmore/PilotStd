/**
 * 标准号解析为结构化字段（回落方案，仅当 scan 结果中无 logical_code/number/year 时使用）
 * @example "GB/T 19001—2020" → { logical_code: "GB/T", number: 19001, year: 2020 }
 */
export function parseStandardNumber(stdNum: string): {
  logical_code: string; number: number; year: number
} | null {
  if (!stdNum) return null

  // 匹配模式：字母前缀 + 空格 + 数字 + 分隔符(—/-/:) + 四位年份
  // 覆盖：GB/T 19001—2020、GB 12345-2020、ISO 9001:2015、DB31/T 123—2022
  const match = stdNum.match(/^([A-Z][A-Z0-9/]+)\s*(\d+(?:\.\d+)?)\s*[—\-:]\s*(\d{4})$/)
  if (!match) return null

  const number = parseInt(match[2], 10)
  const year = parseInt(match[3], 10)

  if (isNaN(number) || isNaN(year)) return null

  return {
    logical_code: match[1].trim(),
    number,
    year,
  }
}
