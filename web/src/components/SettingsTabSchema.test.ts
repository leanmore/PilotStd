// SettingsTabSchema：按 tabKey 从注入的 schema 映射取字段渲染卡片；标题走 i18n，未知 tab 回退 key
import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import SettingsTabSchema from './SettingsTabSchema.vue'
import DynamicSettingField from './DynamicSettingField.vue'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

// 用仓库已有的 key（translations 存在）作字段 key，避免测试输出 i18n 缺键告警
const TABS = {
  storage: [{ key: 'cache.usage' }, { key: 'cache.status' }],
  network: [{ key: 'cache.rows' }],
}

function mountTab(tabKey: string, tabs: unknown = TABS, locale = 'zh-CN') {
  const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
  return mount(SettingsTabSchema, {
    props: { tabKey },
    global: {
      plugins: [PrimeVue, i18n],
      provide: { settingsSchemaTabs: tabs, settingsSchema: {}, settingsConfig: {} },
    },
  })
}

describe('SettingsTabSchema', () => {
  it('tabKey 有字段：渲染卡片、i18n 标题与对应数量的动态字段', () => {
    const w = mountTab('storage')
    expect(w.find('.card-header').text()).toBe('存储设置')
    expect(w.findAllComponents(DynamicSettingField)).toHaveLength(2)
    expect(w.findAllComponents(DynamicSettingField)[0].props('fieldKey')).toBe('cache.usage')
  })

  it('tabKey 无字段：整张卡片不渲染（空 tab 不占位）', () => {
    const w = mountTab('not-exist')
    expect(w.html()).toBe('<!--v-if-->')
  })

  it('未登记的 tabKey 有字段时，卡片标题回退显示原始 key', () => {
    const w = mountTab('custom', { custom: [{ key: 'cache.usage' }] })
    expect(w.find('.card-header').text()).toBe('custom')
  })

  it('tabKey prop 变化时标题与字段整体切换', async () => {
    const w = mountTab('storage')
    await w.setProps({ tabKey: 'network' })
    expect(w.find('.card-header').text()).toBe('网络设置')
    expect(w.findAllComponents(DynamicSettingField)).toHaveLength(1)
    expect(w.findAllComponents(DynamicSettingField)[0].props('fieldKey')).toBe('cache.rows')
  })

  it('语言切换后标题重新翻译（en → Storage Settings）', () => {
    expect(mountTab('storage', TABS, 'en').find('.card-header').text()).toBe('Storage Settings')
  })

  it('注入的是 ref 时保持响应式：外部更新映射表后字段随之刷新', async () => {
    const tabs = ref<Record<string, Array<{ key: string }>>>({ storage: [{ key: 'cache.usage' }] })
    const w = mountTab('storage', tabs)
    expect(w.findAllComponents(DynamicSettingField)).toHaveLength(1)

    tabs.value = { storage: [{ key: 'cache.usage' }, { key: 'cache.status' }, { key: 'cache.rows' }] }
    await w.vm.$nextTick()
    expect(w.findAllComponents(DynamicSettingField)).toHaveLength(3)
  })
})
