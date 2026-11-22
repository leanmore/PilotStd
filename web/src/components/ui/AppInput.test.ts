// AppInput 单测（DS 阶段二 · 模块一）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppInput from './AppInput.vue'

/** 挂 PrimeVue：AppInput 内部就是 PrimeVue 原语，缺 config 会在渲染期取不到 $primevue */
function mountInput(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppInput, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppInput', () => {
  it('默认 size=m / type=text，渲染 PrimeVue InputText', () => {
    const w = mountInput()
    expect(w.classes()).toContain('app-input--m')
    expect(w.classes()).toContain('app-input--text')
    expect(w.find('input.p-inputtext').exists()).toBe(true)
  })

  it('三档尺寸各自映射到对应 class', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountInput({ size })
      expect(w.classes()).toContain(`app-input--${size}`)
    }
  })

  it('v-model 双向：输入触发 update:modelValue', async () => {
    const w = mountInput({ modelValue: '' })
    await w.find('input').setValue('PilotStd')
    expect(w.emitted('update:modelValue')).toHaveLength(1)
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['PilotStd'])
  })

  it('清空时归一为 ""（InputText 回传 undefined，对外不抖动）', async () => {
    const w = mountInput({ modelValue: 'abc' })
    await w.find('input').setValue('')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([''])
  })

  it('modelValue 透传为 input 的 value', () => {
    const w = mountInput({ modelValue: 'GB/T 1-2020' })
    expect((w.find('input').element as HTMLInputElement).value).toBe('GB/T 1-2020')
  })

  it('disabled 透传到内部 input', () => {
    const w = mountInput({ disabled: true })
    expect(w.find('input').attributes('disabled')).toBeDefined()
  })

  it('invalid 加 class 并透传 aria-invalid', () => {
    const w = mountInput({ invalid: true })
    expect(w.classes()).toContain('app-input--invalid')
    expect(w.find('input').attributes('aria-invalid')).toBe('true')
  })

  it('bare 时不施加基础 class，只留 bare 标记', () => {
    const w = mountInput({ bare: true })
    expect(w.classes()).toContain('app-input--bare')
    expect(w.classes()).not.toContain('app-input--m')
    expect(w.classes()).not.toContain('app-input')
  })

  it('$attrs 透传（placeholder / id / name / type）', () => {
    const w = mountInput({}, { placeholder: '请输入', id: 'cron-input', name: 'cron', type: 'text' })
    const input = w.find('input')
    expect(input.attributes('placeholder')).toBe('请输入')
    expect(input.attributes('id')).toBe('cron-input')
    expect(input.attributes('name')).toBe('cron')
    expect(input.attributes('type')).toBe('text')
  })
})

/**
 * type 分叉（2026-11-22 解冻补齐）。
 *
 * 背景：no-raw-input.js 的报错文案与 ui-system.md §11.5 契约表都承诺
 * `<AppInput type="textarea" :rows="n">` / `<AppInput type="number">` 合法。
 * 若 type 只经 $attrs 落到原生 input 上，textarea 会被**静默降级**成单行框
 * （不报错、测试也过），number 回传字符串且 min/step 无人消费 —— 故这里逐条锁死。
 */
describe('AppInput · type 分叉', () => {
  it('type=textarea 渲染真正的 <textarea>（不是降级成 input）', () => {
    const w = mountInput({ type: 'textarea', modelValue: '' })
    expect(w.find('textarea.p-textarea').exists()).toBe(true)
    expect(w.find('input').exists()).toBe(false)
    expect(w.classes()).toContain('app-input--textarea')
  })

  it('type=textarea 时 rows 生效', () => {
    const w = mountInput({ type: 'textarea', rows: 5 })
    expect(w.find('textarea').attributes('rows')).toBe('5')
  })

  it('type=textarea 默认 rows=3', () => {
    const w = mountInput({ type: 'textarea' })
    expect(w.find('textarea').attributes('rows')).toBe('3')
  })

  it('type=textarea 回传 string（与单行一致）', async () => {
    const w = mountInput({ type: 'textarea', modelValue: '' })
    await w.find('textarea').setValue('多行\n文本')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['多行\n文本'])
  })

  it('type=number 渲染 PrimeVue InputNumber，回传 number 而非 string', async () => {
    const w = mountInput({ type: 'number', modelValue: null })
    const input = w.find('input.p-inputnumber-input')
    expect(input.exists()).toBe(true)
    expect(w.classes()).toContain('app-input--number')

    // InputNumber 不在每次按键时写值（内部保留格式化中间态），
    // 而是在 blur / Enter / spin 时 updateModel —— 故这里 setValue 后必须 blur
    await input.setValue('42')
    await input.trigger('blur')
    const emitted = w.emitted('update:modelValue')?.[0]
    expect(emitted).toHaveLength(1)
    // 关键断言：类型必须是 number（回传 '42' 会让下游 Number.isFinite 静默失效）
    expect(typeof emitted?.[0]).toBe('number')
    expect(emitted?.[0]).toBe(42)
  })

  it('type=number 清空时回传 null（不是 ""，保持 allowEmpty 语义）', async () => {
    const w = mountInput({ type: 'number', modelValue: 42 })
    const input = w.find('input.p-inputnumber-input')
    await input.setValue('')
    await input.trigger('blur')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([null])
  })

  it('type=number 显式透传 showButtons / min / max / step / minFractionDigits', () => {
    const w = mountInput({
      type: 'number',
      modelValue: 5,
      showButtons: true,
      min: 1,
      max: 10,
      step: 2,
      minFractionDigits: 1,
    })
    const num = w.findComponent({ name: 'InputNumber' })
    expect(num.props('showButtons')).toBe(true)
    expect(num.props('min')).toBe(1)
    expect(num.props('max')).toBe(10)
    expect(num.props('step')).toBe(2)
    expect(num.props('minFractionDigits')).toBe(1)
  })

  it('type=password + toggleMask 切到 PrimeVue Password 并关掉强度提示', () => {
    const w = mountInput({ type: 'password', toggleMask: true, modelValue: '' })
    expect(w.find('.p-password').exists()).toBe(true)
    expect(w.find('input.p-password-input').exists()).toBe(true)
    expect(w.classes()).toContain('app-input--password')
    expect(w.findComponent({ name: 'Password' }).props('feedback')).toBe(false)
    expect(w.findComponent({ name: 'Password' }).props('toggleMask')).toBe(true)
  })

  it('type=password 不带 toggleMask 时用 InputText + type=password（不渲染 Password 外壳）', () => {
    const w = mountInput({ type: 'password', modelValue: '' })
    expect(w.find('.p-password').exists()).toBe(false)
    expect(w.find('input[type="password"]').exists()).toBe(true)
  })

  it('type=password 回传 string', async () => {
    const w = mountInput({ type: 'password', toggleMask: true, modelValue: '' })
    await w.find('input.p-password-input').setValue('s3cret')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['s3cret'])
  })

  it('四个分叉共用四态 class 口径（invalid 在每种 type 下都生效）', () => {
    for (const type of ['text', 'password', 'number', 'textarea'] as const) {
      const w = mountInput({ type, size: 's', invalid: true, toggleMask: type === 'password' })
      expect(w.classes(), `${type} 缺 invalid class`).toContain('app-input--invalid')
      // 尺寸 class：textarea 刻意不挂（见下一条用例），其余三种必须挂
      if (type === 'textarea') {
        expect(w.classes(), 'textarea 不应挂尺寸 class').not.toContain('app-input--s')
      } else {
        expect(w.classes(), `${type} 缺 size class`).toContain('app-input--s')
      }
    }
  })

  /**
   * P0 缺陷 B 回归：textarea 被固定高度压成单行。
   *
   * 尺寸类 `.app-input--m` 带 `height: var(--input-height-md)`（34px），而
   * `.app-input--textarea` 只有 `min-height` —— min-height 压不过 height，
   * 于是 rows=5 的多行框实际只显示一行。修法是 textarea 分叉不挂尺寸类。
   * 这里锁死「不挂固定高度类」这个前提，避免以后有人为了"统一尺寸口径"把尺寸类加回来。
   */
  it('type=textarea 不挂固定高度尺寸类（rows 撑高，不被压成单行）', () => {
    for (const size of ['l', 'm', 's'] as const) {
      const w = mountInput({ type: 'textarea', size, rows: 5 })
      expect(w.classes(), `textarea 不应挂 app-input--${size}`).not.toContain(`app-input--${size}`)
      expect(w.classes()).toContain('app-input--textarea')
      // 基础外观类仍要在（描边/圆角/四态都挂在 .app-input 上）
      expect(w.classes()).toContain('app-input')
      expect(w.find('textarea').attributes('rows')).toBe('5')
    }
  })

  /**
   * P0 缺陷 A 回归：不装 PrimeVue 插件时不得崩溃。
   *
   * `@primevue/core` 的 `BaseInput.$variant` 是 `this.variant ?? this.$primevue.config.inputStyle`，
   * variant 为 null 时**无条件**读 `$primevue.config`。本仓有一类只测文案的用例
   * （src/views/CommonI18n.test.ts 的 RegisterView / RouteDebugPanel）故意不装插件，
   * 于是 AppInput 一渲染就抛 `Cannot read properties of undefined (reading 'config')`。
   * 四个分叉显式传 variant="outlined" 后 $variant 短路；这里直接复现该场景并锁死。
   *
   * 边界（如实登记，不掩盖）：password + toggleMask 分叉走 PrimeVue Password，
   * 它的 `mounted()` 里读 `this.$primevue.config.locale.passwordPrompt`（与 variant 无关），
   * 故该形态**必须**有 PrimeVue 插件（生产由 main.ts 全局安装，恒满足）。
   * 其余三态（text / number / textarea）在无插件环境下必须能渲染。
   */
  it('未安装 PrimeVue 插件时 text / number / textarea 分叉都能渲染（variant 短路 $primevue.config）', () => {
    const cases = [
      { type: 'text', modelValue: '' },
      { type: 'number', modelValue: 1 },
      { type: 'textarea', modelValue: '' },
    ] as const
    for (const c of cases) {
      const w = mount(AppInput, { props: { type: c.type, modelValue: c.modelValue } })
      expect(w.find('input, textarea').exists(), `${c.type} 未渲染出输入元素`).toBe(true)
    }
  })

  it('四个分叉都显式传 variant="outlined"（缺陷 A 的修法本体）', () => {
    const cases = [
      { type: 'text', comp: 'InputText' },
      { type: 'number', comp: 'InputNumber' },
      { type: 'textarea', comp: 'Textarea' },
      { type: 'password', comp: 'Password', toggleMask: true },
    ] as const
    for (const c of cases) {
      const w = mountInput({ type: c.type, modelValue: '', toggleMask: 'toggleMask' in c })
      const inner = w.findComponent({ name: c.comp })
      expect(inner.exists(), `${c.comp} 未渲染`).toBe(true)
      expect(inner.props('variant'), `${c.comp} 缺 variant`).toBe('outlined')
    }
  })

  it('type=date / time / email 等原生 type 原样透传（走 InputText，不降级成 text）', () => {
    for (const type of ['date', 'time', 'email', 'tel', 'url', 'search'] as const) {
      const w = mountInput({ type })
      expect(w.find(`input[type="${type}"]`).exists(), `${type} 未透传`).toBe(true)
      expect(w.classes()).toContain(`app-input--${type}`)
    }
  })

  it('type=number 透传 maxFractionDigits（固定精度显示，如 25 → 25.00）', () => {
    const w = mountInput({ type: 'number', modelValue: 25, minFractionDigits: 2, maxFractionDigits: 2 })
    const num = w.findComponent({ name: 'InputNumber' })
    expect(num.props('minFractionDigits')).toBe(2)
    expect(num.props('maxFractionDigits')).toBe(2)
  })

  /**
   * inputClass 透传（fix-d2 在 SettingsTabSites 用到的编辑态高亮）。
   *
   * AppInput 不声明 inputClass prop，故 `:input-class` 落进 $attrs，再由 `v-bind="$attrs"`
   * 作为 InputNumber 的 inputClass prop 传下去 —— PrimeVue 会把它加到内层
   * `.p-inputnumber-input` 上（InputNumber.vue 的 `:class="[cx('pcInputText'), inputClass]"`）。
   * 即：调用方**不需要**改写成根 class + :deep() 穿透，`:input-class` 本就能用。
   * 这里锁死该路径，避免以后有人把 $attrs 绑定挪走或改成显式白名单时静默失效。
   */
  it('type=number 时 :input-class 经 $attrs 落到 InputNumber 的 inputClass', () => {
    const w = mountInput({ type: 'number', modelValue: 1 }, { inputClass: 'edit-input' })
    const num = w.findComponent({ name: 'InputNumber' })
    expect(num.props('inputClass')).toBe('edit-input')
    expect(w.find('input.p-inputnumber-input').classes()).toContain('edit-input')
  })
})

/**
 * 结构性类型（2026-11-22 补齐，fix-c4 报的阻塞项）。
 *
 * ui-system.md §11.4 明确要求「type="file" 的隐藏上传域、type="radio" 的单选…走 <AppInput bare>」。
 * 两条都要锁死，否则替换时会出现「不报错但功能静默失效」：
 *  1. `type` 枚举必须收下 file/radio/hidden/checkbox（否则 vue-tsc 直接 TS2322）；
 *  2. `type` 必须**原样透传**给原生 input —— 早期实现写成 `type === 'password' ? 'password' : 'text'`，
 *     会把 file 渲染成 text（上传域彻底失效）、radio 渲染成文本框（视觉全崩）。
 */
describe('AppInput · 结构性类型（bare 逃生舱）', () => {
  it('type=file 原样透传为 <input type="file">（不被降级成 text）', () => {
    const w = mountInput({ type: 'file', bare: true }, { accept: 'image/*' })
    const input = w.find('input')
    expect(input.attributes('type')).toBe('file')
    expect(input.attributes('accept')).toBe('image/*')
  })

  it('type=radio 原样透传为 <input type="radio">，value/checked 经 $attrs 落地', () => {
    const w = mountInput({ type: 'radio', bare: true }, { value: '50', checked: true, name: 'size' })
    const input = w.find('input')
    expect(input.attributes('type')).toBe('radio')
    expect(input.attributes('value')).toBe('50')
    expect(input.attributes('name')).toBe('size')
    expect(input.attributes('checked')).toBeDefined()
  })

  it('type=hidden 原样透传', () => {
    const w = mountInput({ type: 'hidden', bare: true }, { name: 'csrf' })
    expect(w.find('input').attributes('type')).toBe('hidden')
  })

  it('结构性类型配 bare 时不带任何 DS 基础 class', () => {
    const w = mountInput({ type: 'file', bare: true })
    expect(w.classes()).toContain('app-input--bare')
    expect(w.classes()).not.toContain('app-input')
    expect(w.classes()).not.toContain('app-input--file')
  })
})
