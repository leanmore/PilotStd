// TableLoadFooter：分页底部四态互斥（加载中/全显示/可加载全部/滚动提示）+ loadAll 事件
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import TableLoadFooter from './TableLoadFooter.vue'
import zhCN from '@/locales/zh-CN.json'

type FooterProps = { displayed: number; total: number; isLoading: boolean; showLoadAllButton: boolean }

function mountFooter(props: FooterProps) {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(TableLoadFooter, { props, global: { plugins: [i18n] } })
}

const base: FooterProps = { displayed: 50, total: 200, isLoading: false, showLoadAllButton: false }

describe('TableLoadFooter', () => {
  it('total=0 时整块不渲染（空表不显示底栏）', () => {
    expect(mountFooter({ ...base, total: 0 }).html()).toBe('<!--v-if-->')
  })

  it('加载中：显示"加载更多标准..."并渲染 spinner', () => {
    const w = mountFooter({ ...base, isLoading: true })
    expect(w.text()).toContain('加载更多标准...')
    expect(w.find('.spinner').exists()).toBe(true)
    expect(w.find('.load-all-btn').exists()).toBe(false)
  })

  it('已全部显示：显示"已显示全部 N 条标准"，不渲染加载按钮', () => {
    const w = mountFooter({ ...base, displayed: 200 })
    expect(w.text()).toContain('已显示全部 200 条标准')
    expect(w.find('.load-all-btn').exists()).toBe(false)
  })

  it('可加载全部：显示部分进度与剩余条数按钮，点击 emit loadAll', async () => {
    const w = mountFooter({ ...base, displayed: 100, showLoadAllButton: true })
    expect(w.text()).toContain('已显示前 100 / 200 条标准')
    expect(w.find('.load-all-btn').text()).toContain('加载剩余 100 条')

    await w.find('.load-all-btn').trigger('click')
    expect(w.emitted('loadAll')).toHaveLength(1)
  })

  it('未开启"加载全部"按钮：显示滚动提示而非按钮', () => {
    const w = mountFooter({ ...base, displayed: 50 })
    expect(w.text()).toContain('显示 50 / 200 条，滚动加载更多')
    expect(w.find('.load-all-btn').exists()).toBe(false)
  })

  it('isLoading 优先级最高：即使 displayed>=total 也显示加载中', () => {
    const w = mountFooter({ ...base, displayed: 200, isLoading: true })
    expect(w.text()).toContain('加载更多标准...')
    expect(w.text()).not.toContain('已显示全部')
  })
})
