import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SchedulerStatus from './SchedulerStatus.vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Badge from 'primevue/badge'
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
  props: ['value', 'stripedRows', 'size', 'loading'],
}

function mountComponent() {
  return shallowMount(SchedulerStatus, {
    global: {
      stubs: { Card: StubCard, Button, Badge, DataTable: StubDataTable },
    },
  })
}

describe('SchedulerStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title 调度器状态', () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { running: false, job_count: 0, jobs: [], timestamp: '2026-06-30T00:00:00Z' },
    })
    const wrapper = mountComponent()
    expect(wrapper.find('.page-title').text()).toBe('调度器状态')
  })

  it('shows Badge as 已停止 when scheduler is not running', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { running: false, job_count: 0, jobs: [], timestamp: '2026-06-30T00:00:00Z' },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const badge = wrapper.findComponent(Badge)
    expect(badge.exists()).toBe(true)
    expect(badge.props('value')).toBe('已停止')
    expect(badge.props('severity')).toBe('danger')
  })

  it('shows Badge as 运行中 when scheduler is running', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { running: true, job_count: 3, jobs: [], timestamp: '2026-06-30T00:00:00Z' },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const badge = wrapper.findComponent(Badge)
    expect(badge.props('value')).toBe('运行中')
    expect(badge.props('severity')).toBe('success')
  })

  it('renders job count from API response', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { running: true, job_count: 5, jobs: [], timestamp: '2026-06-30T00:00:00Z' },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.html()).toContain('任务数: 5')
  })

  it('passes empty jobs array to DataTable', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { running: false, job_count: 0, jobs: [], timestamp: '' },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const dt = wrapper.findComponent(StubDataTable)
    expect(dt.props('value')).toEqual([])
  })
})
