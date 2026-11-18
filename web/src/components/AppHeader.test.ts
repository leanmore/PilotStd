// AppHeader：Popover 打开期间顶栏必须保持显示（铃铛弹层锚点不能变 0）
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { defineComponent } from 'vue'
import AppHeader from './AppHeader.vue'
import zhCN from '@/locales/zh-CN.json'

const BellStub = defineComponent({
  name: 'NotificationBell',
  emits: ['popover-show', 'popover-hide'],
  template: '<button class="bell-stub">bell</button>',
})

function mountHeader() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(AppHeader, {
    props: { isMobile: false, sidebarCollapsed: false, pageTitle: '首页', isDark: false, username: 'u' },
    global: { plugins: [i18n], stubs: { NotificationBell: BellStub } },
  })
}

describe('AppHeader 顶栏显示条件', () => {
  it('hover 显示、离开隐藏；Popover 打开期间不因 mouseleave 隐藏', async () => {
    const wrapper = mountHeader()
    const right = wrapper.find('.topbar-right')
    expect(right.attributes('style') || '').toContain('display: none')

    await wrapper.find('header').trigger('mouseenter')
    expect(right.attributes('style') || '').not.toContain('display: none')

    const bell = wrapper.findComponent({ name: 'NotificationBell' })
    bell.vm.$emit('popover-show')
    await wrapper.find('header').trigger('mouseleave')
    expect(right.attributes('style') || '').not.toContain('display: none')

    bell.vm.$emit('popover-hide')
    await wrapper.vm.$nextTick()
    expect(right.attributes('style') || '').toContain('display: none')
  })
})
