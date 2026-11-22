// AppCheckbox 单测（DS 阶段二 · 模块一）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppCheckbox from './AppCheckbox.vue'

function mountCheckbox(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppCheckbox, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppCheckbox', () => {
  it('默认 size=m，渲染 PrimeVue Checkbox（.p-checkbox 结构）', () => {
    const w = mountCheckbox()
    expect(w.classes()).toContain('app-checkbox--m')
    expect(w.find('.p-checkbox').exists()).toBe(true)
  })

  it('三档尺寸各自映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountCheckbox({ size })
      expect(w.classes()).toContain(`app-checkbox--${size}`)
    }
  })

  it('v-model 双向（binary）：点击触发 update:modelValue', async () => {
    const w = mountCheckbox({ modelValue: false, binary: true })
    await w.find('input[type="checkbox"]').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual([true])
  })

  it('v-model 双向（多选数组）：勾选后回传含 value 的数组', async () => {
    const w = mountCheckbox({ modelValue: [], value: 'a' })
    await w.find('input[type="checkbox"]').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual([['a']])
  })

  it('modelValue 透传为勾选态', () => {
    const w = mountCheckbox({ modelValue: true, binary: true })
    expect((w.find('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('disabled 透传到内部 input 并加 .p-disabled', () => {
    const w = mountCheckbox({ disabled: true })
    expect(w.find('input[type="checkbox"]').attributes('disabled')).toBeDefined()
    expect(w.classes()).toContain('p-disabled')
  })

  it('invalid 加 class 并透传 aria-invalid', () => {
    const w = mountCheckbox({ invalid: true })
    expect(w.classes()).toContain('app-checkbox--invalid')
    expect(w.find('input[type="checkbox"]').attributes('aria-invalid')).toBe('true')
  })

  it('bare 时不施加基础 class，只留 bare 标记', () => {
    const w = mountCheckbox({ bare: true })
    expect(w.classes()).toContain('app-checkbox--bare')
    expect(w.classes()).not.toContain('app-checkbox--m')
    expect(w.classes()).not.toContain('app-checkbox')
  })

  it('$attrs 透传（id → 根节点，inputId → 内部 input，name / value → input）', () => {
    // PrimeVue 的约定：id 落在根 div（供 <label for> 指向可点击区域），
    // inputId 才是原生 input 的 id。两者都靠 $attrs 原样透传，组件不吞。
    const w = mountCheckbox({}, { id: 'chk-1', inputId: 'chk-1-input', name: 'events', value: 'notify' })
    expect(w.attributes('id')).toBe('chk-1')
    const input = w.find('input[type="checkbox"]')
    expect(input.attributes('id')).toBe('chk-1-input')
    expect(input.attributes('name')).toBe('events')
    expect((input.element as HTMLInputElement).value).toBe('notify')
  })
})
