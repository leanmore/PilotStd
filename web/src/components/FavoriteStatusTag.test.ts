// web/src/components/FavoriteStatusTag.test.ts
// 收藏下载状态标签的边界契约：未收藏不渲染；已收藏即便无队列行也要渲染"未加入队列"

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import Tag from 'primevue/tag'
import { createI18n } from 'vue-i18n'
import FavoriteStatusTag from './FavoriteStatusTag.vue'
import zhCN from '@/locales/zh-CN.json'

const LONG_ERROR = '采标标准，版权受限，自动跳过：' + 'y'.repeat(200)

function mountTag(props: Record<string, unknown>) {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(FavoriteStatusTag, {
    props,
    global: { plugins: [PrimeVue, i18n], components: { Tag } },
  })
}

function fields(over: Record<string, unknown> = {}) {
  return {
    download_status: 'done',
    download_error: null,
    last_attempt: '2026-03-01',
    download_updated_at: '2026-03-01 00:00:00',
    ...over,
  }
}

describe('FavoriteStatusTag 边界契约', () => {
  it('status 为 null/undefined（未收藏或他人不可见）→ 什么都不渲染', () => {
    expect(mountTag({ status: null }).html()).toBe('<!--v-if-->')
    expect(mountTag({}).html()).toBe('<!--v-if-->')
  })

  it('status 为对象 → 渲染对应下载状态标签', () => {
    expect(mountTag({ status: fields({ download_status: 'done' }) }).text()).toContain('已归档')
    expect(mountTag({ status: fields({ download_status: 'failed' }) }).text()).toContain('下载失败')
    expect(mountTag({ status: fields({ download_status: 'abandoned' }) }).text()).toContain('已放弃')
  })

  it('status 存在但 download_status 为 null（已收藏但无队列行）→ 渲染"未加入队列"，不空白', () => {
    const wrapper = mountTag({ status: fields({ download_status: null }) })
    expect(wrapper.text()).toContain('未加入队列')
    expect(wrapper.text()).not.toContain('已入队')  // 不得与"排队中"混淆
    expect(wrapper.findComponent(Tag).exists()).toBe(true)
  })

  it('未知枚举值回退显示原文', () => {
    expect(mountTag({ status: fields({ download_status: 'brand_new' }) }).text()).toContain('brand_new')
  })

  it('showError 时展示截断后的失败原因，全量在 title 中', () => {
    const wrapper = mountTag({ status: fields({ download_status: 'failed', download_error: LONG_ERROR }), showError: true })
    const html = wrapper.html()
    expect(html).toContain(LONG_ERROR.slice(0, 120) + '…')
    expect(html).toContain(`title="${LONG_ERROR}"`)
  })

  it('showError 关闭时不展示失败原因正文（公告详情页列窄）', () => {
    const wrapper = mountTag({ status: fields({ download_status: 'failed', download_error: LONG_ERROR }) })
    expect(wrapper.text()).not.toContain(LONG_ERROR.slice(0, 20))
  })

  it('标签悬停提示含最后尝试时间', () => {
    const wrapper = mountTag({ status: fields({ download_status: 'failed', last_attempt: '2026-03-01' }) })
    expect(wrapper.html()).toContain('2026-03-01')
  })
})
