import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'
import StandardTable from './StandardTable.vue'

/** 用真实 locale 文件挂载（空 messages 会让 t() 回显 key，断言即失去意义） */
function makeI18n(locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

function mountTable(props: Record<string, unknown>, locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN') {
  return mount(StandardTable, {
    props,
    global: {
      plugins: [PrimeVue, makeI18n(locale)],
      components: { DataTable, Column },
    },
  })
}

describe('StandardTable', () => {
  it('renders with empty data', () => {
    const wrapper = mountTable({ data: [] })
    const dt = wrapper.findComponent({ name: 'DataTable' })
    expect(dt.exists()).toBe(true)
    expect(wrapper.findAllComponents({ name: 'Column' }).length).toBe(4)
  })

  it('renders rows for data', () => {
    const data = [
      { standard_number: 'GB/T 1-2020', standard_name: '基础规范', status: '现行', source_site: 'std_gov' },
      { standard_number: 'GB 713-2014', standard_name: '锅炉', status: '废止', source_site: 'njbz365' },
    ]
    const wrapper = mountTable({ data })
    const dt = wrapper.findComponent({ name: 'DataTable' })
    expect(dt.exists()).toBe(true)
    expect(dt.props('value')).toEqual(data)
  })

  // 批 6 i18n 守卫：列头文案确实来自 locales，且随语言切换而变化
  it('列头文案随语言切换（zh-CN / en）', () => {
    const zh = mountTable({ data: [] }, 'zh-CN')
    expect(zh.html()).toContain('标准号')

    const english = mountTable({ data: [] }, 'en')
    expect(english.html()).toContain('Standard No.')
    expect(english.html()).not.toContain('standard_table.')
  })
})
