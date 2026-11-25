// web/src/lib/primevueLocale.test.ts
// primevueLocale.ts 是纯数据模块（语言 → PrimeVue Calendar 语言包）：没有回退函数，
// 未知语言查表得到 undefined。回退由调用方完成：
//   main.ts（日期面板全局配置）：primevueLocales[savedLocale] || primevueLocales['en']
//   AppCalendar.vue：primevueLocales[locale] || primevueLocales['zh-CN']
// 本测试锁定数据契约（字段 / 数组长度 / 首日 / 格式）与调用方兜底语义。
import { describe, expect, it } from 'vitest'

import { primevueLocales } from './primevueLocale'

const LANG_KEYS = ['zh-CN', 'en', 'zh-TW']
const REQUIRED_STRING_FIELDS = ['today', 'clear', 'dateFormat', 'weekHeader']

describe('primevueLocales 语言 → locale 对象映射', () => {
  it('只提供 zh-CN / en / zh-TW 三套语言包', () => {
    expect(Object.keys(primevueLocales).sort()).toEqual([...LANG_KEYS].sort())
  })

  it('每套语言包字段齐全且数组长度合法（PrimeVue Calendar 必需字段）', () => {
    for (const lang of LANG_KEYS) {
      const loc = primevueLocales[lang]
      expect(typeof loc.firstDayOfWeek, `${lang}.firstDayOfWeek`).toBe('number')
      expect(loc.dayNames, `${lang}.dayNames`).toHaveLength(7)
      expect(loc.dayNamesShort, `${lang}.dayNamesShort`).toHaveLength(7)
      expect(loc.dayNamesMin, `${lang}.dayNamesMin`).toHaveLength(7)
      expect(loc.monthNames, `${lang}.monthNames`).toHaveLength(12)
      expect(loc.monthNamesShort, `${lang}.monthNamesShort`).toHaveLength(12)
      for (const field of REQUIRED_STRING_FIELDS) {
        expect(typeof loc[field], `${lang}.${field}`).toBe('string')
      }
    }
  })

  it('首日约定：中文（zh-CN / zh-TW）周一为首日 = 1，英文周日为首日 = 0', () => {
    expect(primevueLocales['zh-CN'].firstDayOfWeek).toBe(1)
    expect(primevueLocales['zh-TW'].firstDayOfWeek).toBe(1)
    expect(primevueLocales.en.firstDayOfWeek).toBe(0)
  })

  it('中文两套共享月份名，zh-TW 用繁体星期简称与「週」表头', () => {
    expect(primevueLocales['zh-TW'].monthNames).toEqual(primevueLocales['zh-CN'].monthNames)
    expect(primevueLocales['zh-TW'].dayNamesShort).toContain('週日')
    expect(primevueLocales['zh-CN'].dayNamesShort).toContain('周日')
    expect(primevueLocales['zh-TW'].weekHeader).toBe('週')
    expect(primevueLocales['zh-CN'].weekHeader).toBe('周')
  })

  it('日期格式：中文 yy-mm-dd，英文 mm/dd/yy', () => {
    expect(primevueLocales['zh-CN'].dateFormat).toBe('yy-mm-dd')
    expect(primevueLocales['zh-TW'].dateFormat).toBe('yy-mm-dd')
    expect(primevueLocales.en.dateFormat).toBe('mm/dd/yy')
  })

  it('文案不串味：英文包是英文，中文包是中文', () => {
    expect(primevueLocales.en.today).toBe('Today')
    expect(primevueLocales.en.dayNames[0]).toBe('Sunday')
    expect(primevueLocales.en.monthNames[0]).toBe('January')
    expect(primevueLocales['zh-CN'].today).toBe('今天')
    expect(primevueLocales['zh-CN'].dayNames[0]).toBe('星期日')
  })
})

describe('未知语言回退', () => {
  it('未知语言查表返回 undefined，不抛错', () => {
    expect(primevueLocales['fr-FR']).toBeUndefined()
    expect(primevueLocales['']).toBeUndefined()
    expect(primevueLocales['zh-cn']).toBeUndefined() // 大小写敏感，调用方须传标准 locale
  })

  it('调用方兜底 `|| primevueLocales[\'en\']`（main.ts）：未知语言回退英文包', () => {
    const savedLocale = 'fr-FR'
    expect(primevueLocales[savedLocale] || primevueLocales['en']).toBe(primevueLocales.en)
  })

  it('调用方兜底 `|| primevueLocales[\'zh-CN\']`（AppCalendar.vue）：未知语言回退中文包', () => {
    const locale = 'fr-FR'
    expect(primevueLocales[locale] || primevueLocales['zh-CN']).toBe(primevueLocales['zh-CN'])
  })
})
