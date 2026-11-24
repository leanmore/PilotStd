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

/**
 * 断言「没有把语言包当成属性下发」：PrimeVue 4.5 DatePicker 没有 `locale` prop，
 * 传下去只会变成非法 DOM 属性（`locale="[object Object]"`），且对面板无效。
 */
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
  it('中文：挂载后同步 PrimeVue 全局 locale（面板只认全局配置）', () => {
    const { wrapper } = mountCalendar('zh-CN')
    expect(primevueLocale(wrapper)).toEqual(primevueLocales['zh-CN'])
    expect(primevueLocale(wrapper).today).toBe('今天')
    // D-3 回归：不得把语言包当作 `locale` 属性下发给 DatePicker
    expect(passedLocale(wrapper)).toBeUndefined()
  })

  it('英文：全局 locale 切到 en', () => {
    const { wrapper } = mountCalendar('en')
    expect(primevueLocale(wrapper).today).toBe('Today')
  })

  it('运行时切换 i18n.locale（不重挂载）：watch 更新全局 locale（D-3 回归）', async () => {
    const { wrapper, i18n } = mountCalendar('zh-CN')
    expect(primevueLocale(wrapper).today).toBe('今天')

    i18n.global.locale.value = 'en'
    await wrapper.vm.$nextTick()

    // 原缺陷：只在 onMounted 设置一次 → 切语言后面板仍是中文
    expect(primevueLocale(wrapper).today).toBe('Today')
  })

  it('未知 locale 回退 zh-CN，不把 undefined 写进全局 locale', () => {
    const { wrapper } = mountCalendar('fr')
    expect(primevueLocale(wrapper)).toEqual(primevueLocales['zh-CN'])
  })

  it('$attrs 透传到内部 DatePicker 的输入框（业务侧无需关心包装层）', () => {
    const { wrapper } = mountCalendar('zh-CN', { placeholder: '选择日期', disabled: true })
    const input = wrapper.find('input')
    expect(input.attributes('placeholder')).toBe('选择日期')
    expect(input.attributes('disabled')).toBeDefined()
  })
})
