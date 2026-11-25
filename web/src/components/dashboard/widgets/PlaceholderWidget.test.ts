// PlaceholderWidget：标题优先取 widget.config.title，缺省走 i18n 默认；开发中提示随语言切换
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PlaceholderWidget from './PlaceholderWidget.vue'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

type WidgetProp = { config?: { title?: string } }

function mountWidget(widget: WidgetProp, locale = 'zh-CN') {
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  return mount(PlaceholderWidget, { props: { widget }, global: { plugins: [i18n] } })
}

describe('PlaceholderWidget', () => {
  it('widget.config.title 优先作为卡片标题', () => {
    const w = mountWidget({ config: { title: '自定义看板' } })
    expect(w.find('.widget-header').text()).toBe('自定义看板')
  })

  it('无 widget 配置时标题回退 i18n 默认"卡片"', () => {
    const w = mountWidget({})
    expect(w.find('.widget-header').text()).toBe('卡片')
    expect(w.text()).not.toContain('undefined')
  })

  it('config 存在但 title 为空时同样回退默认标题', () => {
    const w = mountWidget({ config: { title: '' } })
    expect(w.find('.widget-header').text()).toBe('卡片')
  })

  it('始终渲染"开发中"提示，且随语言切换', () => {
    expect(mountWidget({}).text()).toContain('此卡片功能正在开发中')
    expect(mountWidget({}, 'en').text()).toContain('This card is under development')
  })

  it('英文环境下默认标题切换为 Card', () => {
    expect(mountWidget({}, 'en').find('.widget-header').text()).toBe('Card')
  })
})
