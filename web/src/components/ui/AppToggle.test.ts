// AppToggle 单测（DS 阶段二 · 模块一）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppToggle from './AppToggle.vue'

function mountToggle(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppToggle, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppToggle', () => {
  it('默认 size=m，渲染 PrimeVue ToggleSwitch（role=switch）', () => {
    const w = mountToggle()
    expect(w.classes()).toContain('app-toggle--m')
    expect(w.find('.p-toggleswitch').exists()).toBe(true)
    expect(w.find('input[role="switch"]').exists()).toBe(true)
  })

  it('三档尺寸各自映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountToggle({ size })
      expect(w.classes()).toContain(`app-toggle--${size}`)
    }
  })

  it('v-model 双向：切换触发 update:modelValue', async () => {
    const w = mountToggle({ modelValue: false })
    await w.find('input[role="switch"]').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual([true])
  })

  it('modelValue=true 时标记 checked 并加 .p-toggleswitch-checked', () => {
    const w = mountToggle({ modelValue: true })
    expect(w.classes()).toContain('p-toggleswitch-checked')
    expect((w.find('input[role="switch"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('trueValue / falseValue 经 $attrs 透传（不靠组件猜）', async () => {
    const w = mountToggle({ modelValue: 'off' }, { trueValue: 'on', falseValue: 'off' })
    await w.find('input[role="switch"]').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['on'])
  })

  it('disabled 透传到内部 input 并加 .p-disabled', () => {
    const w = mountToggle({ disabled: true })
    expect(w.find('input[role="switch"]').attributes('disabled')).toBeDefined()
    expect(w.classes()).toContain('p-disabled')
  })

  it('invalid 加 class 并透传 aria-invalid', () => {
    const w = mountToggle({ invalid: true })
    expect(w.classes()).toContain('app-toggle--invalid')
    expect(w.find('input[role="switch"]').attributes('aria-invalid')).toBe('true')
  })

  it('bare 时不施加基础 class，只留 bare 标记', () => {
    const w = mountToggle({ bare: true })
    expect(w.classes()).toContain('app-toggle--bare')
    expect(w.classes()).not.toContain('app-toggle--m')
    expect(w.classes()).not.toContain('app-toggle')
  })

  it('$attrs 透传（id → 根节点，inputId → 内部 switch，name / aria-label → input）', () => {
    // 与 Checkbox 同一约定：id 落根 div，inputId 才是原生 input 的 id（<label for> 指根节点）
    const w = mountToggle(
      {},
      { id: 'sw-1', inputId: 'sw-1-input', name: 'enabled', 'aria-label': '启用通知' },
    )
    expect(w.attributes('id')).toBe('sw-1')
    const input = w.find('input[role="switch"]')
    expect(input.attributes('id')).toBe('sw-1-input')
    expect(input.attributes('aria-label')).toBe('启用通知')
    expect(w.findComponent({ name: 'ToggleSwitch' }).props('name')).toBe('enabled')
  })
})
