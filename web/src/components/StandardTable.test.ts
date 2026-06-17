import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import StandardTable from './StandardTable.vue'

describe('StandardTable', () => {
  it('renders with empty data', () => {
    const wrapper = mount(StandardTable, {
      props: { data: [] },
      global: {
        plugins: [PrimeVue],
        // PrimeVue v4 不全局注册组件，需在 mount 时显式注册
        components: { DataTable, Column },
      },
    })
    // DataTable 组件挂载后应存在
    const dt = wrapper.findComponent({ name: 'DataTable' })
    expect(dt.exists()).toBe(true)
    // 应有 4 个 Column 列定义
    expect(wrapper.findAllComponents({ name: 'Column' }).length).toBe(4)
  })

  it('renders rows for data', () => {
    const data = [
      { standard_number: 'GB/T 1-2020', standard_name: '基础规范', status: '现行', source_site: 'std_gov' },
      { standard_number: 'GB 713-2014', standard_name: '锅炉', status: '废止', source_site: 'njbz365' },
    ]
    const wrapper = mount(StandardTable, {
      props: { data },
      global: {
        plugins: [PrimeVue],
        components: { DataTable, Column },
      },
    })
    // 验证 DataTable 收到正确的 value prop
    const dt = wrapper.findComponent({ name: 'DataTable' })
    expect(dt.exists()).toBe(true)
    expect(dt.props('value')).toEqual(data)
  })
})
