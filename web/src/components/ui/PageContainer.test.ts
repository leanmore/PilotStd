// PageContainer 单测（DS 阶段三 · 模块三）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import PageContainer from './PageContainer.vue'

describe('PageContainer', () => {
  it('默认渲染 page-container 类，且不加 flush / padded', () => {
    const w = mount(PageContainer, { slots: { default: '页面内容' } })
    expect(w.classes()).toContain('page-container')
    expect(w.classes()).not.toContain('page-container--flush')
    expect(w.classes()).not.toContain('page-container--padded')
    expect(w.text()).toContain('页面内容')
  })

  it('默认不加左右内边距（左右留给 AppLayout 的 .content-inner，避免双倍留白）', () => {
    const w = mount(PageContainer)
    // 组件默认不设 inline padding，由 CSS 的 padding-inline: 0 保证
    expect(w.element.style.paddingInline).toBe('')
  })

  it('flush 时加 flush 类（全宽页面）', () => {
    const w = mount(PageContainer, { props: { flush: true } })
    expect(w.classes()).toContain('page-container--flush')
  })

  it('padded 时加 padded 类（显式开启左右留白）', () => {
    const w = mount(PageContainer, { props: { padded: true } })
    expect(w.classes()).toContain('page-container--padded')
  })

  it('title 渲染成 h2.page-title（统一排版，替代 8 个 views 里重复的 CSS）', () => {
    const w = mount(PageContainer, { props: { title: '公告管理' } })
    const h2 = w.find('h2.page-title')
    expect(h2.exists()).toBe(true)
    expect(h2.text()).toBe('公告管理')
  })

  it('subtitle 渲染成副标题小字', () => {
    const w = mount(PageContainer, { props: { title: 'T', subtitle: '说明文字' } })
    expect(w.find('.page-container__subtitle').text()).toBe('说明文字')
  })

  it('maxWidth 数字自动补 px，字符串原样', () => {
    const num = mount(PageContainer, { props: { maxWidth: 900 } })
    expect(num.element.style.maxWidth).toBe('900px')

    const str = mount(PageContainer, { props: { maxWidth: '60rem' } })
    expect(str.element.style.maxWidth).toBe('60rem')
  })

  it('maxWidth 为 null 时不设 max-width', () => {
    const w = mount(PageContainer)
    expect(w.element.style.maxWidth).toBe('')
  })

  it('#title 插槽可完全接管标题区', () => {
    const w = mount(PageContainer, {
      props: { title: '不应出现' },
      slots: { title: '<span class="custom-title">自定义标题</span>' },
    })
    expect(w.find('.custom-title').exists()).toBe(true)
    expect(w.find('h2.page-title').exists()).toBe(false)
  })

  it('#actions 插槽渲染在标题右侧', () => {
    const w = mount(PageContainer, {
      props: { title: 'T' },
      slots: { actions: '<button class="act">操作</button>' },
    })
    expect(w.find('.page-container__actions .act').exists()).toBe(true)
  })

  it('透传 $attrs 到根元素', () => {
    const w = mount(PageContainer, { attrs: { 'data-testid': 'page-x' } })
    expect(w.attributes('data-testid')).toBe('page-x')
  })
})
