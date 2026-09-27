import { describe, it, expect, vi, beforeEach } from 'vitest'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import SchedulerStatus from './SchedulerStatus.vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Badge from 'primevue/badge'
import DataTable from 'primevue/datatable'
import { getSchedulerStatus } from '@/api/scheduler'

vi.mock('@/api/scheduler', () => ({
  getSchedulerStatus: vi.fn(),
}))
const mockedGetSchedulerStatus = vi.mocked(getSchedulerStatus)

const StubCard = {
  name: 'Card',
  template: '<div class="card-stub"><slot name="content" /></div>',
}

const StubDataTable = {
  name: 'DataTable',
  template: '<div class="datatable-stub"><slot v-for="item in value" name="body" :data="item" /></div>',
  props: ['value', 'stripedRows', 'size', 'loading'],
}

function makeI18n(locale: 'zh-CN' | 'en') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
}

function mountComponent(locale: 'zh-CN' | 'en' = 'zh-CN') {
  return shallowMount(SchedulerStatus, {
    global: {
      plugins: [makeI18n(locale)],
      stubs: { Card: StubCard, Button, Badge, DataTable: StubDataTable },
    },
  })
}

describe('SchedulerStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title 调度器状态', () => {
    mockedGetSchedulerStatus.mockResolvedValueOnce({
      data: { running: false, job_count: 0, jobs: [], timestamp: '2026-06-30T00:00:00Z' },
    })
    const wrapper = mountComponent()
    expect(wrapper.find('.page-title').text()).toBe('调度器状态')
  })

  it('shows Badge as 已停止 when scheduler is not running', async () => {
    mockedGetSchedulerStatus.mockResolvedValueOnce({
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
    mockedGetSchedulerStatus.mockResolvedValueOnce({
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
    mockedGetSchedulerStatus.mockResolvedValueOnce({
      data: { running: true, job_count: 5, jobs: [], timestamp: '2026-06-30T00:00:00Z' },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.html()).toContain('任务数: 5')
  })

  it('passes empty jobs array to DataTable', async () => {
    mockedGetSchedulerStatus.mockResolvedValueOnce({
      data: { running: false, job_count: 0, jobs: [], timestamp: '' },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const dt = wrapper.findComponent(StubDataTable)
    expect(dt.props('value')).toEqual([])
  })

  it('切换语言到 en 后文案随之变化（i18n 生效）', async () => {
    const zh = mountComponent('zh-CN')
    await nextTick()
    expect(zh.find('.page-title').text()).toBe('调度器状态')

    const english = mountComponent('en')
    await nextTick()
    expect(english.find('.page-title').text()).toBe('Scheduler Status')
  })
})
