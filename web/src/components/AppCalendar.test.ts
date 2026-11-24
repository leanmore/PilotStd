// AppCalendar：语言包计算（i18n.locale → primevueLocales，未知 locale 回退 zh-CN）、
// 挂载时同步 PrimeVue 全局 locale（DatePicker 4.5 无 locale prop，月份面板只认全局配置）、attrs 透传
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import AppCalendar from './AppCalendar.vue'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import { primevueLocales } from '@/lib/primevueLocale'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

function mountCalendar(locale: string, attrs: Record<string, unknown> = {}) {
  const i18n = createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'zh-CN',
    messages: { 'zh-CN': zhCN, en },
  })
  const wrapper = mount(AppCalendar, { attrs, global: { plugins: [PrimeVue, i18n] } })
  return { wrapper, i18n }
}

/** AppCalendar 把语言包作为非 prop 属性传给 AppDatePicker（后者再交给 DatePicker） */
function passedLocale(wrapper: ReturnType<typeof mount>) {
  const attrs = wrapper.getComponent(AppDatePicker).vm.$attrs as Record<string, unknown>
  return attrs.locale
}

/** PrimeVue 的全局语言包对象：onMounted 里直接改写它，月份/星期面板才会跟着变 */
function primevueLocale(wrapper: ReturnType<typeof mount>) {
  const app = (wrapper.vm as unknown as { $: { appContext: { app: { config: { globalProperties: { $primevue: { config: { locale: unknown } } } } } } } }).$.appContext.app
  return app.config.globalProperties.$primevue.config.locale as Record<string, unknown>
}

describe('AppCalendar', () => {
  it('中文：计算出的语言包是 zh-CN，挂载后同步 PrimeVue 全局 locale', () => {
    const { wrapper } = mountCalendar('zh-CN')
    expect(passedLocale(wrapper)).toEqual(primevueLocales['zh-CN'])
    expect(primevueLocale(wrapper)).toEqual(primevueLocales['zh-CN'])
    expect(primevueLocale(wrapper).today).toBe('今天')
  })

  it('英文：语言包与全局 locale 都切到 en', () => {
    const { wrapper } = mountCalendar('en')
    expect(passedLocale(wrapper)).toEqual(primevueLocales.en)
    expect(primevueLocale(wrapper).today).toBe('Today')
  })

  it('运行时切换 i18n.locale：computed 重算，下发给 DatePicker 的语言包随之变化', async () => {
    const { wrapper, i18n } = mountCalendar('zh-CN')
    i18n.global.locale.value = 'en'
    await wrapper.vm.$nextTick()
    expect(passedLocale(wrapper)).toEqual(primevueLocales.en)
  })

  it('未知 locale 回退 zh-CN，不把 undefined 传给 DatePicker', () => {
    const { wrapper } = mountCalendar('fr')
    expect(passedLocale(wrapper)).toEqual(primevueLocales['zh-CN'])
    expect(primevueLocale(wrapper)).toEqual(primevueLocales['zh-CN'])
  })

  it('$attrs 透传到内部 DatePicker 的输入框（业务侧无需关心包装层）', () => {
    const { wrapper } = mountCalendar('zh-CN', { placeholder: '选择日期', disabled: true })
    const input = wrapper.find('input')
    expect(input.attributes('placeholder')).toBe('选择日期')
    expect(input.attributes('disabled')).toBeDefined()
  })
})
