// AppButton 单测（DS 阶段一）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AppButton from './AppButton.vue'

describe('AppButton', () => {
  it('默认是 secondary / m 档', () => {
    const w = mount(AppButton, { slots: { default: '确定' } })
    expect(w.classes()).toContain('app-btn--secondary')
    expect(w.classes()).toContain('app-btn--m')
    expect(w.text()).toBe('确定')
  })

  it('四种层级各自映射到对应 class', () => {
    for (const type of ['primary', 'secondary', 'danger', 'ghost'] as const) {
      const w = mount(AppButton, { props: { type } })
      expect(w.classes()).toContain(`app-btn--${type}`)
    }
  })

  it('三档尺寸各自映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mount(AppButton, { props: { size } })
      expect(w.classes()).toContain(`app-btn--${size}`)
    }
  })

  it('label 渲染为文本，icon 渲染为 <i>', () => {
    const w = mount(AppButton, { props: { label: '刷新', icon: 'pi pi-sync' } })
    expect(w.text()).toBe('刷新')
    expect(w.find('i.pi.pi-sync').exists()).toBe(true)
  })

  it('loading 时禁用点击、显示转圈并标记 aria-busy', () => {
    const w = mount(AppButton, { props: { loading: true } })
    expect(w.attributes('disabled')).toBeDefined()
    expect(w.attributes('aria-busy')).toBe('true')
    expect(w.find('i.pi-spinner').exists()).toBe(true)
  })

  it('disabled 时不派发 click 事件', async () => {
    const w = mount(AppButton, { props: { disabled: true } })
    await w.trigger('click')
    expect(w.emitted('click')).toBeUndefined()
  })

  it('正常状态派发 click 事件', async () => {
    const w = mount(AppButton)
    await w.trigger('click')
    expect(w.emitted('click')).toHaveLength(1)
  })

  it('block 时加满宽 class', () => {
    const w = mount(AppButton, { props: { block: true } })
    expect(w.classes()).toContain('app-btn--block')
  })

  it('默认 type=button（防止在表单里意外提交）', () => {
    const w = mount(AppButton)
    expect(w.attributes('type')).toBe('button')
  })

  it('透传 aria-label 等属性', () => {
    const w = mount(AppButton, { attrs: { 'aria-label': '关闭' } })
    expect(w.attributes('aria-label')).toBe('关闭')
  })
})
