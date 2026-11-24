// SettingsTabAppearanceMixed：登录背景校验/回写、主题切换（点击+键盘）、语言选择与上传回调
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import SettingsTabAppearanceMixed from './SettingsTabAppearanceMixed.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { useAppStore } from '@/stores/app'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

const LOCALE_OPTIONS = [{ label: '中文', value: 'zh-CN' }, { label: 'English', value: 'en' }]

function mountTab(bg = '', locale = 'zh-CN') {
  const values: Record<string, unknown> = { 'appearance.login_bg': bg }
  const getp = vi.fn((path: string) => values[path])
  const setp = vi.fn((path: string, val: unknown) => { values[path] = val })
  const onUploadBg = vi.fn()
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  const wrapper = mount(SettingsTabAppearanceMixed, {
    props: { selectedLocale: 'zh-CN', localeOptions: LOCALE_OPTIONS, onUploadBg },
    global: { plugins: [pinia, PrimeVue, i18n], provide: { settingsGetp: getp, settingsSetp: setp } },
  })
  return { wrapper, getp, setp, onUploadBg, store: useAppStore() }
}

describe('SettingsTabAppearanceMixed', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('渲染卡片标题，并用注入的 getp 回填登录背景地址', () => {
    const { wrapper, getp } = mountTab('https://cdn.example.com/bg.png')
    expect(wrapper.find('.card-header').text()).toBe('界面设置')
    expect(getp).toHaveBeenCalledWith('appearance.login_bg')
    expect(wrapper.findAllComponents(AppInput)[0].props('modelValue')).toBe('https://cdn.example.com/bg.png')
  })

  it('合法网络地址：写回 settingsSetp，且不显示错误', async () => {
    const { wrapper, setp } = mountTab()
    wrapper.findAllComponents(AppInput)[0].vm.$emit('update:modelValue', 'https://x/bg.jpg')
    await wrapper.vm.$nextTick()

    expect(setp).toHaveBeenCalledWith('appearance.login_bg', 'https://x/bg.jpg')
    expect(wrapper.find('.field-error').exists()).toBe(false)
  })

  it('本地 file:// 路径：拒绝写入（回写空串）并显示明确错误', async () => {
    const { wrapper, setp } = mountTab()
    wrapper.findAllComponents(AppInput)[0].vm.$emit('update:modelValue', 'file:///C:/bg.png')
    await wrapper.vm.$nextTick()

    expect(setp).toHaveBeenCalledWith('appearance.login_bg', '')
    expect(wrapper.find('.field-error').text()).toContain('不支持本地文件路径')
  })

  it('点击主题项：写入 app store 并更新 active/aria-checked', async () => {
    const { wrapper, store } = mountTab()
    const options = wrapper.findAll('.theme-option')
    expect(options).toHaveLength(4)

    await options[1].trigger('click')
    expect(store.theme).toBe('dark')
    expect(wrapper.findAll('.theme-option')[1].classes()).toContain('active')
    expect(wrapper.findAll('.theme-option')[1].attributes('aria-checked')).toBe('true')
    expect(wrapper.findAll('.theme-option')[0].attributes('aria-checked')).toBe('false')
  })

  it('主题项支持键盘 Enter / Space 切换（无障碍）', async () => {
    const { wrapper, store } = mountTab()
    await wrapper.findAll('.theme-option')[2].trigger('keydown.enter')
    expect(store.theme).toBe('green')

    await wrapper.findAll('.theme-option')[3].trigger('keydown.space')
    expect(store.theme).toBe('blue')
  })

  it('切换语言：emit update:selectedLocale 与 localeChange', () => {
    const { wrapper } = mountTab()
    wrapper.findComponent({ name: 'AppSelect' }).vm.$emit('update:modelValue', 'en')
    expect(wrapper.emitted('update:selectedLocale')).toEqual([['en']])
    expect(wrapper.emitted('localeChange')).toHaveLength(1)
  })

  it('上传区域的文件变更事件原样交给父级 onUploadBg 回调', async () => {
    const { wrapper, onUploadBg } = mountTab()
    const fileInput = wrapper.find('input[type="file"]')
    expect(fileInput.exists()).toBe(true)

    await fileInput.trigger('change')
    expect(onUploadBg).toHaveBeenCalledTimes(1)
    expect(onUploadBg.mock.calls[0][0]).toBeInstanceOf(Event)
  })

  it('英文环境下卡片标题与上传文案跟随语言', () => {
    const { wrapper } = mountTab('', 'en')
    expect(wrapper.find('.card-header').text()).toBe('Interface Settings')
    expect(wrapper.text()).toContain('Upload')
  })
})
