// AppDatePicker 单测（DS 阶段二 · 模块一）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppDatePicker from './AppDatePicker.vue'

function mountPicker(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppDatePicker, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppDatePicker', () => {
  it('默认 size=m，渲染 PrimeVue DatePicker（.p-datepicker 结构）', () => {
    const w = mountPicker()
    expect(w.classes()).toContain('app-datepicker--m')
    expect(w.find('.p-datepicker').exists()).toBe(true)
  })

  it('三档尺寸各自映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountPicker({ size })
      expect(w.classes()).toContain(`app-datepicker--${size}`)
    }
  })

  it('v-model 双向：内部 DatePicker 写值触发 update:modelValue', async () => {
    const w = mountPicker({ modelValue: null })
    const d = new Date(2026, 10, 22)
    // 面板 teleport 到 body，直接走内部组件的写值通道（等价于用户点选某一天）
    w.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', d)
    await w.vm.$nextTick()
    expect(w.emitted('update:modelValue')?.[0]).toEqual([d])
  })

  it('modelValue 透传给内部 DatePicker', () => {
    const d = new Date(2026, 10, 22)
    const w = mountPicker({ modelValue: d })
    expect(w.findComponent({ name: 'DatePicker' }).props('modelValue')).toEqual(d)
  })

  it('disabled 加 class 并透传 disabled prop', () => {
    const w = mountPicker({ disabled: true })
    expect(w.classes()).toContain('app-datepicker--disabled')
    expect(w.findComponent({ name: 'DatePicker' }).props('disabled')).toBe(true)
  })

  it('invalid 加 class 并透传 aria-invalid', () => {
    const w = mountPicker({ invalid: true })
    expect(w.classes()).toContain('app-datepicker--invalid')
    expect(w.find('input').attributes('aria-invalid')).toBe('true')
  })

  it('bare 时不施加基础 class，只留 bare 标记', () => {
    const w = mountPicker({ bare: true })
    expect(w.classes()).toContain('app-datepicker--bare')
    expect(w.classes()).not.toContain('app-datepicker--m')
    expect(w.classes()).not.toContain('app-datepicker')
  })

  it('$attrs 透传（placeholder / id / name / showTime）', () => {
    const w = mountPicker({}, { placeholder: '选择日期', id: 'dp-1', name: 'date', showTime: true })
    const picker = w.findComponent({ name: 'DatePicker' })
    expect(picker.props('placeholder')).toBe('选择日期')
    expect(picker.attributes('id')).toBe('dp-1')
    expect(picker.props('name')).toBe('date')
    expect(picker.props('showTime')).toBe(true)
  })
})
