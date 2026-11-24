// UnifiedFilterBar：三类公告筛选 Tab 高亮 + 切换事件 + "至少保留一个启用"守卫
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import UnifiedFilterBar from './UnifiedFilterBar.vue'
import zhCN from '@/locales/zh-CN.json'

type BarProps = { currentTab: string; fetchEnabled: Record<string, boolean> }

function mountBar(props: BarProps) {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(UnifiedFilterBar, { props, global: { plugins: [PrimeVue, i18n] } })
}

const base: BarProps = { currentTab: 'gb', fetchEnabled: { gb: true, hb: true, db: false } }

describe('UnifiedFilterBar', () => {
  it('渲染三类公告标签（用 long 文案而非短标签）', () => {
    const w = mountBar(base)
    expect(w.findAll('.filter-item')).toHaveLength(3)
    expect(w.text()).toContain('国家标准公告')
    expect(w.text()).toContain('行业标准公告')
    expect(w.text()).toContain('地方标准公告')
  })

  it('只有 currentTab 命中的项带 active 类', () => {
    const w = mountBar({ ...base, currentTab: 'hb' })
    const active = w.findAll('.filter-item.active')
    expect(active).toHaveLength(1)
    expect(active[0].text()).toContain('行业标准公告')
  })

  it('点击 Tab 项 emit update:currentTab 并携带对应 key', async () => {
    const w = mountBar(base)
    await w.findAll('.filter-item')[2].trigger('click')
    expect(w.emitted('update:currentTab')).toEqual([['db']])
  })

  it('拨动开关 emit update:fetchEnabled(key, value)', () => {
    const w = mountBar(base)
    w.findAllComponents({ name: 'AppToggle' })[1].vm.$emit('update:modelValue', false)
    expect(w.emitted('update:fetchEnabled')).toEqual([['hb', false]])
  })

  it('只启用一个时不允许关掉最后一个（守卫：不发任何事件）', () => {
    const w = mountBar({ currentTab: 'gb', fetchEnabled: { gb: true, hb: false, db: false } })
    w.findAllComponents({ name: 'AppToggle' })[0].vm.$emit('update:modelValue', false)
    expect(w.emitted('update:fetchEnabled')).toBeUndefined()
  })

  it('点击开关不冒泡触发 Tab 切换（@click.stop）', async () => {
    const w = mountBar(base)
    await w.findAllComponents({ name: 'AppToggle' })[0].trigger('click')
    expect(w.emitted('update:currentTab')).toBeUndefined()
  })
})
