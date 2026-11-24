// AppSidebar：展开/折叠两形态的导航渲染、active 命中、折叠按钮事件与提示文案
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import AppSidebar from './AppSidebar.vue'
import zhCN from '@/locales/zh-CN.json'

const NAV = [
  { label: '首页', icon: 'pi pi-home', to: '/' },
  { label: '任务', icon: 'pi pi-play', to: '/task' },
]
const routes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/task', component: { template: '<div />' } },
]

async function mountSidebar(over: Record<string, unknown> = {}) {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/task')
  await router.isReady()
  return mount(AppSidebar, {
    props: { sidebarCollapsed: false, navItems: NAV, routePath: '/task', ...over },
    global: { plugins: [i18n, router] },
  })
}

describe('AppSidebar', () => {
  it('展开态：品牌名与全部导航文案可见，导航项按 navItems 渲染', async () => {
    const w = await mountSidebar()
    expect(w.find('.brand-text').text()).toBe('PilotStd')
    expect(w.findAll('.nav-item')).toHaveLength(2)
    expect(w.find('.brand-text').isVisible()).toBe(true)
    expect(w.findAll('.nav-label').map((n) => n.text())).toEqual(['首页', '任务'])
    expect(w.findAll('.nav-item')[0].attributes('title')).toBe('')
  })

  it('active 只命中 routePath 对应的导航项', async () => {
    const w = await mountSidebar()
    const active = w.findAll('.nav-item.active')
    expect(active).toHaveLength(1)
    expect(active[0].text()).toContain('任务')
  })

  it('折叠态：aside 带 collapsed 类，品牌文字与导航文案隐藏，title 补位为标签', async () => {
    const w = await mountSidebar({ sidebarCollapsed: true })
    expect(w.find('aside').classes()).toContain('collapsed')
    expect(w.find('.brand-text').isVisible()).toBe(false)
    expect(w.findAll('.nav-label')[1].isVisible()).toBe(false)
    expect(w.findAll('.nav-item')[1].attributes('title')).toBe('任务')
  })

  it('点击折叠按钮 emit toggle-collapse', async () => {
    const w = await mountSidebar()
    await w.find('.collapse-toggle').trigger('click')
    expect(w.emitted('toggle-collapse')).toHaveLength(1)
  })

  it('折叠按钮的 title 随状态在"收起/展开"之间切换', async () => {
    const expanded = await mountSidebar()
    expect(expanded.find('.collapse-toggle').attributes('title')).toBe('收起')

    const collapsed = await mountSidebar({ sidebarCollapsed: true })
    expect(collapsed.find('.collapse-toggle').attributes('title')).toBe('展开')
  })

  it('折叠态仍渲染全部导航项（只是文字隐藏），避免导航丢失', async () => {
    const w = await mountSidebar({ sidebarCollapsed: true })
    expect(w.findAll('.nav-item')).toHaveLength(2)
    expect(w.html()).toContain('pi pi-home')
    expect(w.html()).toContain('pi pi-play')
  })
})
