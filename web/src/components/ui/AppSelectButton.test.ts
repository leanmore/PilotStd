// AppSelectButton 单测（DS 阶段二 · 模块一扩展：分段单选）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppSelectButton from './AppSelectButton.vue'

const OPTIONS = [
  { label: '追加', value: 'append' },
  { label: '替换', value: 'replace' },
]

function mountSelectButton(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppSelectButton, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppSelectButton', () => {
  it('默认 size=m，渲染 PrimeVue SelectButton 的分段结构（role=group + 多个 p-togglebutton）', () => {
    const w = mountSelectButton({ options: OPTIONS, optionLabel: 'label', optionValue: 'value' })
    expect(w.classes()).toContain('app-selectbutton--m')
    // 分段单选的关键特征：所有选项同时可见（不是下拉）
    expect(w.find('[role="group"]').exists()).toBe(true)
    expect(w.findAll('button.p-togglebutton')).toHaveLength(2)
    expect(w.find('.p-select').exists()).toBe(false)
  })

  it('三档尺寸各自映射到对应 class，并映射 PrimeVue 的 small/large', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountSelectButton({ options: OPTIONS, size })
      expect(w.classes()).toContain(`app-selectbutton--${size}`)
    }
    const inner = (size: string) => mountSelectButton({ options: OPTIONS, size }).findComponent({ name: 'SelectButton' })
    expect(inner('s').props('size')).toBe('small')
    expect(inner('l').props('size')).toBe('large')
    // m 档不传 PrimeVue 的 size（Aura 默认档）；未传时 PrimeVue 归一为 null
    expect(inner('m').props('size')).toBeFalsy()
  })

  it('options / optionLabel / optionValue 透传到 SelectButton', () => {
    const w = mountSelectButton({ options: OPTIONS, optionLabel: 'label', optionValue: 'value' })
    const inner = w.findComponent({ name: 'SelectButton' })
    expect(inner.props('options')).toEqual(OPTIONS)
    expect(inner.props('optionLabel')).toBe('label')
    expect(inner.props('optionValue')).toBe('value')
  })

  it('v-model 双向：点选未选中项触发 update:modelValue（回传 optionValue 值）', async () => {
    const w = mountSelectButton({
      modelValue: 'append',
      options: OPTIONS,
      optionLabel: 'label',
      optionValue: 'value',
    })
    await w.findAll('button.p-togglebutton')[1].trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['replace'])
  })

  it('重复点选当前项：默认 allowEmpty=true（与迁移前 PrimeVue 默认一致，不改变交互语义）', async () => {
    const w = mountSelectButton({
      modelValue: 'append',
      options: OPTIONS,
      optionLabel: 'label',
      optionValue: 'value',
    })
    await w.findAll('button.p-togglebutton')[0].trigger('click')
    // PrimeVue 默认 allowEmpty=true ⇒ 再点已选项会清空；本封装不改这个默认值，
    // 保证「替换前后交互形态一致」——业务若要禁止清空，显式传 :allow-empty="false"。
    expect(w.emitted('update:modelValue')?.[0]).toEqual([null])
  })

  it('allowEmpty 经 $attrs 透传（:allow-empty="false" 时再点已选项不清空）', async () => {
    const w = mountSelectButton(
      { modelValue: 'append', options: OPTIONS, optionLabel: 'label', optionValue: 'value' },
      { allowEmpty: false },
    )
    await w.findAll('button.p-togglebutton')[0].trigger('click')
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })

  it('modelValue 决定选中态（p-togglebutton-checked / aria-pressed）', () => {
    const w = mountSelectButton({
      modelValue: 'replace',
      options: OPTIONS,
      optionLabel: 'label',
      optionValue: 'value',
    })
    const buttons = w.findAll('button.p-togglebutton')
    expect(buttons[0].classes()).not.toContain('p-togglebutton-checked')
    expect(buttons[1].classes()).toContain('p-togglebutton-checked')
    expect(buttons[1].attributes('aria-pressed')).toBe('true')
  })

  it('multiple 透传：多选时回传数组', async () => {
    const w = mountSelectButton({
      modelValue: ['append'],
      options: OPTIONS,
      optionLabel: 'label',
      optionValue: 'value',
      multiple: true,
    })
    expect(w.findComponent({ name: 'SelectButton' }).props('multiple')).toBe(true)
    await w.findAll('button.p-togglebutton')[1].trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([['append', 'replace']])
  })

  it('disabled 加 class 且所有分段按钮不可点', () => {
    const w = mountSelectButton({ options: OPTIONS, optionLabel: 'label', disabled: true })
    expect(w.classes()).toContain('app-selectbutton--disabled')
    for (const btn of w.findAll('button.p-togglebutton')) {
      expect(btn.attributes('disabled')).toBeDefined()
    }
  })

  it('invalid 加 class 并透传 invalid prop', () => {
    const w = mountSelectButton({ options: OPTIONS, invalid: true })
    expect(w.classes()).toContain('app-selectbutton--invalid')
    expect(w.findComponent({ name: 'SelectButton' }).props('invalid')).toBe(true)
  })

  it('bare 时不施加基础 class，只留 bare 标记', () => {
    const w = mountSelectButton({ options: OPTIONS, bare: true })
    expect(w.classes()).toContain('app-selectbutton--bare')
    expect(w.classes()).not.toContain('app-selectbutton--m')
    expect(w.classes()).not.toContain('app-selectbutton')
  })

  it('$attrs 透传（id / aria-labelledby 落到根节点）', () => {
    const w = mountSelectButton(
      { options: OPTIONS },
      { id: 'update-mode', 'aria-labelledby': 'update-mode-label' },
    )
    expect(w.attributes('id')).toBe('update-mode')
    expect(w.attributes('aria-labelledby')).toBe('update-mode-label')
  })
})
