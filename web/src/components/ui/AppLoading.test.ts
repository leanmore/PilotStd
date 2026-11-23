// AppLoading 单测（DS 阶段三 · 模块四）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AppLoading from './AppLoading.vue'

describe('AppLoading', () => {
  it('默认形态是 spinner，带 role=status 与 aria-live', () => {
    const w = mount(AppLoading)
    expect(w.classes()).toContain('app-loading--spinner')
    expect(w.attributes('role')).toBe('status')
    expect(w.attributes('aria-live')).toBe('polite')
    expect(w.find('.app-loading__ring').exists()).toBe(true)
  })

  it('三档尺寸映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mount(AppLoading, { props: { size } })
      expect(w.classes()).toContain(`app-loading--${size}`)
    }
  })

  it('label 有值时渲染文案，空值不渲染', () => {
    const withLabel = mount(AppLoading, { props: { label: '加载中' } })
    expect(withLabel.find('.app-loading__label').text()).toBe('加载中')

    const without = mount(AppLoading)
    expect(without.find('.app-loading__label').exists()).toBe(false)
  })

  it('block 时撑满父容器', () => {
    const w = mount(AppLoading, { props: { block: true } })
    expect(w.classes()).toContain('app-loading--block')
  })

  it('skeleton 形态按 rows 渲染骨架条，并带读屏文案', () => {
    const w = mount(AppLoading, { props: { variant: 'skeleton', rows: 4 } })
    expect(w.classes()).toContain('app-loading--skeleton')
    expect(w.findAll('.app-loading__bar')).toHaveLength(4)
    // 骨架屏无可读内容，必须有 sr-only 文案供读屏
    expect(w.find('.app-loading__sr').exists()).toBe(true)
  })

  it('skeleton 的 rows 默认 3 条', () => {
    const w = mount(AppLoading, { props: { variant: 'skeleton' } })
    expect(w.findAll('.app-loading__bar')).toHaveLength(3)
  })

  it('skeleton 的 rowHeight 支持预设档位（s/m/l）与数字', () => {
    const preset = mount(AppLoading, { props: { variant: 'skeleton', rows: 1, rowHeight: 'l' } })
    expect(preset.find('.app-loading__bar').attributes('style')).toContain('height: var(--size-16)')

    const numeric = mount(AppLoading, { props: { variant: 'skeleton', rows: 1, rowHeight: 24 } })
    expect(numeric.find('.app-loading__bar').attributes('style')).toContain('height: 24px')
  })

  it('inline 形态渲染为 span（不打断行内布局）', () => {
    const w = mount(AppLoading, { props: { variant: 'inline', label: '加载中' } })
    expect(w.element.tagName).toBe('SPAN')
    expect(w.classes()).toContain('app-loading--inline')
    expect(w.find('.app-loading__ring').exists()).toBe(true)
  })

  it('skeleton 形态不渲染转圈（避免双重加载暗示）', () => {
    const w = mount(AppLoading, { props: { variant: 'skeleton' } })
    expect(w.find('.app-loading__ring').exists()).toBe(false)
  })
})
