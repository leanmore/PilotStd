// AppTable 单测（DS 阶段二 · 模块二）
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

import AppTable from './AppTable.vue'

const ROWS = [
  { id: 1, name: 'GB/T 1-2020' },
  { id: 2, name: 'GB 713-2014' },
]

/** 挂 PrimeVue：AppTable 内部就是 PrimeVue DataTable，缺 config 会在渲染期取不到 $primevue */
function mountTable(props: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}) {
  return mount(AppTable, {
    props,
    attrs,
    global: { plugins: [PrimeVue] },
  })
}

describe('AppTable', () => {
  it('渲染 PrimeVue DataTable 并带 DS 根类', () => {
    const w = mountTable({ value: [] })
    expect(w.find('.p-datatable').exists()).toBe(true)
    expect(w.classes()).toContain('app-table')
  })

  it('value 透传到内部 DataTable', () => {
    const w = mountTable({ value: ROWS })
    expect(w.findComponent({ name: 'DataTable' }).props('value')).toEqual(ROWS)
    expect(w.findAll('tbody tr').length).toBe(ROWS.length)
  })

  it('分页相关 props（paginator / rows / totalRecords）原样透传', () => {
    const w = mountTable({ value: ROWS, paginator: true, rows: 20, totalRecords: 99 })
    const dt = w.findComponent({ name: 'DataTable' })
    expect(dt.props('paginator')).toBe(true)
    expect(dt.props('rows')).toBe(20)
    expect(dt.props('totalRecords')).toBe(99)
    // 分页器真的渲染出来了，而不只是 prop 被接住
    expect(w.find('.p-paginator').exists()).toBe(true)
  })

  it('其余常用 props（stripedRows / loading / dataKey / selectionMode）零遗漏透传', () => {
    const w = mountTable({
      value: ROWS,
      stripedRows: true,
      loading: true,
      dataKey: 'id',
      selectionMode: 'multiple',
    })
    const dt = w.findComponent({ name: 'DataTable' })
    expect(dt.props('stripedRows')).toBe(true)
    expect(dt.props('loading')).toBe(true)
    expect(dt.props('dataKey')).toBe('id')
    expect(dt.props('selectionMode')).toBe('multiple')
  })

  it('默认插槽渲染 <Column>（列级插槽 #body 由 Column 自己消费）', () => {
    const w = mount(AppTable, {
      props: { value: ROWS },
      slots: {
        default: `
          <Column field="name" header="标准号">
            <template #body="{ data }"><span class="cell-body">{{ data.name }}</span></template>
          </Column>
        `,
      },
      global: { plugins: [PrimeVue], components: { Column } },
    })
    expect(w.findAllComponents({ name: 'Column' }).length).toBe(1)
    expect(w.find('.cell-body').exists()).toBe(true)
    expect(w.find('.cell-body').text()).toBe('GB/T 1-2020')
    // 表头文案来自 Column 的 header prop
    expect(w.find('thead').text()).toContain('标准号')
  })

  it('#empty 插槽透传（空数据时渲染自定义占位，而不是默认文案）', () => {
    const w = mount(AppTable, {
      props: { value: [] },
      slots: { empty: '<div class="my-empty">暂无数据</div>' },
      global: { plugins: [PrimeVue] },
    })
    expect(w.find('.my-empty').exists()).toBe(true)
    expect(w.find('.my-empty').text()).toBe('暂无数据')
  })

  it('#header / #footer 具名插槽透传', () => {
    const w = mount(AppTable, {
      props: { value: ROWS },
      slots: {
        header: '<div class="my-header">工具栏</div>',
        footer: '<div class="my-footer">共 2 条</div>',
      },
      global: { plugins: [PrimeVue] },
    })
    expect(w.find('.my-header').exists()).toBe(true)
    expect(w.find('.my-footer').exists()).toBe(true)
  })

  it('bare 时不施加基础 class，只留 bare 标记，并走 unstyled', () => {
    const w = mountTable({ value: ROWS, bare: true })
    expect(w.classes()).toContain('app-table--bare')
    expect(w.classes()).not.toContain('app-table')
    expect(w.findComponent({ name: 'DataTable' }).props('unstyled')).toBe(true)
    // unstyled 下 PrimeVue 不再生成 p-datatable 类名（零基础视觉）
    expect(w.find('.p-datatable').exists()).toBe(false)
  })

  it('$attrs 透传事件（@page / @sort 等监听器原样交给 DataTable）', async () => {
    // 事件在 AppTable 上是**透传的监听器**（不是本组件自己的 emit）：
    // v-bind="$attrs" 把 onPage 交给内部 DataTable，DataTable 触发 page 时直接调用它。
    // 所以这里断言"监听器被调用"，而不是 w.emitted('page')（AppTable 从不 $emit 该事件）。
    const pages: unknown[] = []
    const w = mount(AppTable, {
      props: { value: ROWS, paginator: true, rows: 1 },
      attrs: { onPage: (e: unknown) => pages.push(e) },
      global: { plugins: [PrimeVue] },
    })
    const payload = { first: 1, rows: 1, page: 1, pageCount: 2 }
    w.findComponent({ name: 'DataTable' }).vm.$emit('page', payload)
    await w.vm.$nextTick()
    expect(pages).toEqual([payload])
  })

  it('v-model:selection 的 update:selection 监听器同样经 $attrs 透传', async () => {
    const seen: unknown[] = []
    // 键名必须写 `onUpdate:selection`（含冒号）—— 这是 `v-model:selection` 编译出的监听器名；
    // 写成驼峰的 onUpdateSelection 在 Vue 里是另一个属性名，不会命中 DataTable 的 emits。
    const w = mount(AppTable, {
      props: { value: ROWS, selectionMode: 'multiple', dataKey: 'id' },
      attrs: { 'onUpdate:selection': (v: unknown) => seen.push(v) },
      global: { plugins: [PrimeVue] },
    })
    w.findComponent({ name: 'DataTable' }).vm.$emit('update:selection', [ROWS[0]])
    await w.vm.$nextTick()
    expect(seen).toEqual([[ROWS[0]]])
  })

  it('$attrs 透传非 prop 属性（class / data-testid）', () => {
    const w = mountTable({ value: ROWS }, { 'data-testid': 'std-table' })
    expect(w.attributes('data-testid')).toBe('std-table')
    // 业务 class 与 DS class 合并，不覆盖
    const withClass = mountTable({ value: ROWS }, { class: 'mt-2' })
    expect(withClass.classes()).toContain('app-table')
    expect(withClass.classes()).toContain('mt-2')
  })

  it('inheritAttrs: false —— DataTable 的 props 名不会漏成 DOM 属性', () => {
    const w = mountTable({ value: ROWS, stripedRows: true, dataKey: 'id' })
    const root = w.element as HTMLElement
    expect(root.getAttribute('stripedrows')).toBeNull()
    expect(root.getAttribute('datakey')).toBeNull()
    expect(root.getAttribute('value')).toBeNull()
  })
})

describe('AppTable · 组件身份', () => {
  it('显式声明组件名（G-027：防生产构建压缩后组件名丢失）', () => {
    expect(AppTable.name ?? (AppTable as unknown as { __name?: string }).__name).toBe('AppTable')
  })
})
