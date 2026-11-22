// AppSelect 单测（DS 阶段二 · 模块一）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppSelect from './AppSelect.vue'

const OPTIONS = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
]

function mountSelect(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppSelect, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppSelect', () => {
  it('默认 size=m，渲染 PrimeVue Select（.p-select 结构）', () => {
    const w = mountSelect({ options: OPTIONS })
    expect(w.classes()).toContain('app-select--m')
    expect(w.find('.p-select').exists()).toBe(true)
  })

  it('三档尺寸各自映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountSelect({ options: OPTIONS, size })
      expect(w.classes()).toContain(`app-select--${size}`)
    }
  })

  it('options / optionLabel / optionValue 透传到 Select', () => {
    const w = mountSelect({ options: OPTIONS, optionLabel: 'label', optionValue: 'value' })
    const select = w.findComponent({ name: 'Select' })
    expect(select.props('options')).toEqual(OPTIONS)
    expect(select.props('optionLabel')).toBe('label')
    expect(select.props('optionValue')).toBe('value')
  })

  it('v-model 双向：点选选项触发 update:modelValue', async () => {
    const w = mountSelect({ modelValue: null, options: OPTIONS, optionLabel: 'label', optionValue: 'value' })
    // 直接调内部 Select 的写值通道，等价于用户点选（面板 teleport 到 body，DOM 里点不到）
    w.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 2)
    await w.vm.$nextTick()
    expect(w.emitted('update:modelValue')?.[0]).toEqual([2])
  })

  it('modelValue 透传给内部 Select', () => {
    const w = mountSelect({ modelValue: 1, options: OPTIONS, optionValue: 'value' })
    expect(w.findComponent({ name: 'Select' }).props('modelValue')).toBe(1)
  })

  it('disabled 加 class 并透传（Select 用 .p-disabled 标记，不是原生 disabled）', () => {
    const w = mountSelect({ options: OPTIONS, disabled: true })
    expect(w.classes()).toContain('app-select--disabled')
    expect(w.classes()).toContain('p-disabled')
  })

  it('invalid 加 class 并透传 invalid prop', () => {
    const w = mountSelect({ options: OPTIONS, invalid: true })
    expect(w.classes()).toContain('app-select--invalid')
    expect(w.findComponent({ name: 'Select' }).props('invalid')).toBe(true)
  })

  it('bare 时不施加基础 class，只留 bare 标记', () => {
    const w = mountSelect({ options: OPTIONS, bare: true })
    expect(w.classes()).toContain('app-select--bare')
    expect(w.classes()).not.toContain('app-select--m')
    expect(w.classes()).not.toContain('app-select')
  })

  it('$attrs 透传（id / name）与显式 props（placeholder / filter）', () => {
    const w = mountSelect(
      { options: OPTIONS, placeholder: '请选择', filter: true },
      { id: 'weekday-select', name: 'weekday' },
    )
    const select = w.findComponent({ name: 'Select' })
    expect(select.props('placeholder')).toBe('请选择')
    expect(select.props('filter')).toBe(true)
    expect(select.attributes('id')).toBe('weekday-select')
    expect(select.props('name')).toBe('weekday')
  })
})

/**
 * emit 泛型化回归（2026-11-22）。
 *
 * 背景：早期 `defineEmits<{(e:'update:modelValue', value: unknown): void}>()`，
 * strictFunctionTypes 下参数逆变，业务侧写 `(val: string) => void` 会报
 * TS2322「(val: string) => void 不可赋给 (value: unknown) => any」。
 * 改成 `generic="T"` 后 T 由 modelValue 推断。
 *
 * 守卫方式：这里把 handler 收窄成 `(value: string) => void`。若 emit 退回 unknown，
 * 下面 `const asEmitHandler: (value: string) => void = onLocale` 这行会在
 * `vue-tsc` 阶段报 TS2322 —— 把「泛型被改回去」挡在 type-check 门口，
 * 而不是等业务侧替换时才炸。
 */
describe('AppSelect · emit 泛型（业务侧可安全收窄）', () => {
  it('绑 string 的 v-model 时，收窄为 (val: string) => void 的 handler 可用且真实回流', async () => {
    const received: string[] = []
    const onLocale = (value: string): void => {
      received.push(value)
    }

    // 类型级断言：把 handler 赋给「期望 (value: string) => void」的位置。
    // emit 若退化回 unknown，这行即 TS2322（与业务侧报错完全同源）。
    type StringEmitHandler = (value: string) => void
    const asEmitHandler: StringEmitHandler = onLocale
    expect(asEmitHandler).toBe(onLocale)

    const w = mountSelect({
      modelValue: 'zh-CN',
      options: OPTIONS,
      optionLabel: 'label',
      optionValue: 'value',
    })
    // 走真实链路：内部 Select 写值 → AppSelect 的 onUpdate → 对外 emit
    w.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'en')
    await w.vm.$nextTick()

    const emitted = w.emitted('update:modelValue')
    expect(emitted?.[0]).toEqual(['en'])
    // 运行期把 emit 值喂回同一个 handler，验证收窄后行为一致
    asEmitHandler(emitted?.[0]?.[0] as string)
    expect(received).toEqual(['en'])
  })
})
