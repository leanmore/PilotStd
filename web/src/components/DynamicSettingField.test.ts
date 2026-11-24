// DynamicSettingField：schema 驱动的字段类型分叉、嵌套路径读写、数组值保留与缺省回退
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import DynamicSettingField from './DynamicSettingField.vue'
import AppInput from '@/components/ui/AppInput.vue'
import zhCN from '@/locales/zh-CN.json'

type Field = Record<string, unknown>
// 注入的配置对象是运行时任意嵌套 JSON，测试里允许用 any 直接断言写入结果
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Cfg = Record<string, any>

function mountField(fieldKey: string, schema: Record<string, Field> = {}, cfg: Cfg = {}) {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(DynamicSettingField, {
    props: { fieldKey },
    global: {
      plugins: [PrimeVue, i18n],
      provide: { settingsSchema: schema, settingsConfig: cfg },
    },
  })
}

const inputField = (over: Field = {}): Field => ({
  key: 'cache.usage', tab: 'storage', field_type: 'input', default: '', ...over,
})

describe('DynamicSettingField', () => {
  it('文本输入：按注入 schema 的 i18n key 显示标签，值从嵌套路径读取', () => {
    const w = mountField('cache.usage', { 'cache.usage': inputField({ placeholder: 'http://x' }) }, { cache: { usage: 'old' } })
    expect(w.find('.field-label').text()).toContain('使用量')
    const input = w.findComponent(AppInput)
    expect(input.props('modelValue')).toBe('old')
    // placeholder 不是 AppInput 的声明 prop，经 $attrs 落到原生 input
    expect(input.attributes('placeholder')).toBe('http://x')
  })

  it('文本写值就地写入嵌套路径，不丢同级字段', () => {
    const cfg: Cfg = { cache: { usage: 'old', max_size: 50 } }
    const w = mountField('cache.usage', { 'cache.usage': inputField() }, cfg)
    w.findComponent(AppInput).vm.$emit('update:modelValue', 'new')
    expect(cfg.cache).toEqual({ usage: 'new', max_size: 50 })
  })

  it('数字字段：数组值取 [0] 展示；写值保留 [1]（区间配置语义）', () => {
    const cfg: Cfg = { cache: { usage: [5, 3] } }
    const w = mountField('cache.usage', { 'cache.usage': inputField({ field_type: 'number' }) }, cfg)
    const input = w.findComponent(AppInput)
    expect(input.props('type')).toBe('number')
    expect(input.props('modelValue')).toBe(5)

    input.vm.$emit('update:modelValue', 8)
    expect(cfg.cache.usage).toEqual([8, 3])

    input.vm.$emit('update:modelValue', 9)
    expect(cfg.cache.usage).toEqual([9, 3])
  })

  it('开关字段：选中值以字符串 false/true 回传，写入布尔值', () => {
    const cfg: Cfg = { cache: { valid: false } }
    const w = mountField('cache.valid', { 'cache.valid': inputField({ field_type: 'toggle' }) }, cfg)
    const select = w.findComponent({ name: 'AppSelect' })
    expect(select.props('modelValue')).toBe('false')
    expect(select.props('options')).toEqual([
      { label: '否', value: 'false' },
      { label: '是', value: 'true' },
    ])

    select.vm.$emit('update:modelValue', 'true')
    expect(cfg.cache.valid).toBe(true)
  })

  it('下拉字段：options 映射为 label/value，选中值原样写回', () => {
    const cfg: Cfg = { cache: { usage: 'b' } }
    const options = [{ label: '甲', value: 'a' }, { label: '乙', value: 'b' }]
    const w = mountField('cache.usage', { 'cache.usage': inputField({ field_type: 'select', options }) }, cfg)
    const select = w.findComponent({ name: 'AppSelect' })
    expect(select.props('options')).toEqual(options)

    select.vm.$emit('update:modelValue', 'a')
    expect(cfg.cache.usage).toBe('a')
  })

  it('标签字段：数组值逗号展示，输入按逗号切分并 trim/去空', () => {
    const cfg: Cfg = { cache: { usage: ['a', 'b'] } }
    const w = mountField('cache.usage', { 'cache.usage': inputField({ field_type: 'tags' }) }, cfg)
    const input = w.findComponent(AppInput)
    expect(input.props('modelValue')).toBe('a, b')

    input.vm.$emit('update:modelValue', ' x, y ,, z ')
    expect(cfg.cache.usage).toEqual(['x', 'y', 'z'])
  })

  it('密码字段渲染 password 输入；required 与 help_text 一并渲染', () => {
    const w = mountField(
      'cache.usage',
      { 'cache.usage': inputField({ field_type: 'password', required: true, help_text: '填密钥' }) },
      { cache: { usage: 'sec' } },
    )
    expect(w.findComponent(AppInput).props('type')).toBe('password')
    expect(w.find('.required').exists()).toBe(true)
    expect(w.find('.help-text').text()).toBe('填密钥')
  })

  it('schema 缺失时回退为文本输入，标签用 key 末段（下划线转空格）', () => {
    const w = mountField('legacy_field', {}, { legacy_field: 'v' })
    expect(w.find('.field-label').text()).toBe('legacy field')
    expect(w.findComponent(AppInput).props('modelValue')).toBe('v')
  })
})
