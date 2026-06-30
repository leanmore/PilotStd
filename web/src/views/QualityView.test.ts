import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import QualityView from './QualityView.vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import axios from 'axios'

vi.mock('axios')
const mockedAxios = vi.mocked(axios)

const StubCard = {
  name: 'Card',
  template: '<div class="card-stub"><slot name="content" /></div>',
}

const StubDataTable = {
  name: 'DataTable',
  template: '<div class="datatable-stub"><slot v-for="item in value" name="body" :data="item" /></div>',
  props: ['value', 'stripedRows', 'size'],
}

function mountComponent() {
  return shallowMount(QualityView, {
    global: {
      stubs: { Card: StubCard, Button, DataTable: StubDataTable },
    },
  })
}

describe('QualityView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title 数据质量检查', () => {
    const wrapper = mountComponent()
    expect(wrapper.find('.page-title').text()).toBe('数据质量检查')
  })

  it('renders the run check button', () => {
    const wrapper = mountComponent()
    const btn = wrapper.findComponent(Button)
    expect(btn.exists()).toBe(true)
    // 按钮 label 是 "运行检查"
    expect(btn.props('label')).toBe('运行检查')
  })

  it('shows initial prompt before any check is run', () => {
    const wrapper = mountComponent()
    expect(wrapper.html()).toContain('点击「运行检查」开始数据质量检查')
  })

  it('displays check results after running successfully', async () => {
    mockedAxios.post.mockResolvedValueOnce({
      data: {
        ok: true,
        results: [{ rule: 'R001', file: 'a.py', line: 10, severity: 'error', message: 'missing import' }],
        summary: { total: 1, files_checked: 10, passed: false, failed: 1 },
      },
    })
    const wrapper = mountComponent()
    const btn = wrapper.findComponent(Button)
    await btn.trigger('click')
    await nextTick()
    await nextTick()
    // 结果区域应显示违规项
    expect(wrapper.html()).toContain('1 项违规')
    expect(wrapper.html()).toContain('10 文件')
  })

  it('shows last check time after running', async () => {
    vi.useFakeTimers()
    const fakeNow = new Date('2026-06-30T12:00:00Z')
    vi.setSystemTime(fakeNow)
    mockedAxios.post.mockResolvedValueOnce({
      data: { ok: true, results: [], summary: { total: 0, files_checked: 0, passed: true, failed: 0 } },
    })
    const wrapper = mountComponent()
    await wrapper.findComponent(Button).trigger('click')
    await nextTick()
    await nextTick()
    expect(wrapper.find('.text-sm').exists()).toBe(true)
    vi.useRealTimers()
  })
})
