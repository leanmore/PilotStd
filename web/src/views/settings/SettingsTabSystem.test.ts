// SettingsTabSystem 测试
//
// 契约：两个可折叠区域（缓存管理 / 后台任务调度）的显隐完全由父组件传入的
// `sections` prop 决定；折叠头点击只 emit `update:sections`（组件自身不持状态），
// 由父组件统一持久化 —— 否则「应用」与「确定」按钮读到的 sections 会与界面不一致。
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import SettingsTabSystem from './SettingsTabSystem.vue'

const stubs = {
  CacheManager: { name: 'CacheManager', template: '<div class="cache-stub" />' },
  TaskManager: { name: 'TaskManager', template: '<div class="task-stub" />' },
}

function mountTab(sections = { cacheManager: true, taskManager: true }) {
  return mount(SettingsTabSystem, {
    props: { sections },
    global: {
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs,
    },
  })
}

describe('SettingsTabSystem 折叠区域', () => {
  it('渲染两个区域标题与两个子树', () => {
    const wrapper = mountTab()
    const orders = ['缓存管理', '后台任务调度']
    const headers = wrapper.findAll('.collapsible-header')
    expect(headers.length).toBe(2)
    expect(headers.map((h) => h.text())).toEqual(orders)
    expect(wrapper.find('.cache-stub').exists()).toBe(true)
    expect(wrapper.find('.task-stub').exists()).toBe(true)
  })

  it('sections 为 false 时子组件隐藏但保留在 DOM（v-show，不重新挂载）', () => {
    const wrapper = mountTab({ cacheManager: false, taskManager: false })
    expect(wrapper.find('.cache-stub').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'CacheManager' }).isVisible()).toBe(false)
    expect(wrapper.findComponent({ name: 'TaskManager' }).isVisible()).toBe(false)
    // 展开态时可见
    const expanded = mountTab({ cacheManager: true, taskManager: true })
    expect(expanded.findComponent({ name: 'CacheManager' }).isVisible()).toBe(true)
    expect(expanded.findComponent({ name: 'TaskManager' }).isVisible()).toBe(true)
  })

  it('点击缓存区折叠头只翻转 cacheManager，taskManager 原样保留', async () => {
    const wrapper = mountTab({ cacheManager: true, taskManager: false })
    await wrapper.findAll('.collapsible-header')[0].trigger('click')
    const emitted = wrapper.emitted('update:sections')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toEqual({ cacheManager: false, taskManager: false })
  })

  it('点击任务区折叠头只翻转 taskManager', async () => {
    const wrapper = mountTab({ cacheManager: true, taskManager: true })
    await wrapper.findAll('.collapsible-header')[1].trigger('click')
    expect(wrapper.emitted('update:sections')![0][0]).toEqual({ cacheManager: true, taskManager: false })
  })

  it('折叠图标随 sections 变化（pi-chevron-up ↔ pi-chevron-down）', async () => {
    const wrapper = mountTab({ cacheManager: true, taskManager: false })
    const icons = () => wrapper.findAll('.collapsible-icon').map((i) => i.classes())
    expect(icons()[0]).toContain('pi-chevron-up')
    expect(icons()[1]).toContain('pi-chevron-down')
    await wrapper.setProps({ sections: { cacheManager: false, taskManager: true } })
    expect(icons()[0]).toContain('pi-chevron-down')
    expect(icons()[1]).toContain('pi-chevron-up')
  })
})
