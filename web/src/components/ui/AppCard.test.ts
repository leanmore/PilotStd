// AppCard 单测（DS 阶段三 · 模块三）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppCard from './AppCard.vue'

function mountCard(props: Record<string, unknown> = {}, slots: Record<string, string> = {}) {
  return mount(AppCard, {
    props,
    slots,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppCard', () => {
  it('默认渲染 DS 卡片类，不带 elevated', () => {
    const w = mountCard({}, { content: '正文' })
    expect(w.classes()).toContain('app-card')
    expect(w.classes()).not.toContain('app-card--elevated')
    expect(w.text()).toContain('正文')
  })

  it('elevated 时加 elevated 类（阴影升到 --shadow-md）', () => {
    const w = mountCard({ elevated: true })
    expect(w.classes()).toContain('app-card--elevated')
  })

  it('bare 时走 unstyled：只加 bare 类，不加 DS 视觉类', () => {
    const w = mountCard({ bare: true })
    expect(w.classes()).toContain('app-card--bare')
    expect(w.classes()).not.toContain('app-card')
  })

  it('透传 #title / #content / #footer 插槽', () => {
    const w = mountCard({}, { title: '标题', content: '内容', footer: '页脚' })
    const text = w.text()
    expect(text).toContain('标题')
    expect(text).toContain('内容')
    expect(text).toContain('页脚')
  })

  it('透传 $attrs（class / data-testid / aria-label）', () => {
    const w = mountCard({}, {}).findComponent(AppCard)
    // 用 attrs 挂载
    const w2 = mount(AppCard, {
      attrs: { 'data-testid': 'my-card', 'aria-label': '卡片' },
      global: { plugins: [PrimeVue] },
    })
    expect(w2.attributes('data-testid')).toBe('my-card')
    expect(w2.attributes('aria-label')).toBe('卡片')
    expect(w).toBeTruthy()
  })

  it('业务 class 与 DS class 合并（不被覆盖）', () => {
    const w = mount(AppCard, {
      attrs: { class: 'biz-card' },
      global: { plugins: [PrimeVue] },
    })
    expect(w.classes()).toContain('biz-card')
    expect(w.classes()).toContain('app-card')
  })
})
