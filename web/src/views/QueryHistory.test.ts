import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import QueryHistory from './QueryHistory.vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { getQueryResults } from '@/api'

vi.mock('@/api', () => ({
  getQueryResults: vi.fn(),
}))
const mockedGetQueryResults = vi.mocked(getQueryResults)

const StubCard = {
  name: 'Card',
  template: '<div class="card-stub"><slot name="content" /></div>',
}

function mountComponent() {
  return shallowMount(QueryHistory, {
    global: {
      stubs: { Card: StubCard, Button, Tag },
    },
  })
}

describe('QueryHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title 查询历史', () => {
    mockedGetQueryResults.mockResolvedValueOnce({ data: { results: [] } })
    const wrapper = mountComponent()
    expect(wrapper.find('.page-title').text()).toBe('查询历史')
  })

  it('shows empty state when no query history', async () => {
    mockedGetQueryResults.mockResolvedValueOnce({ data: { results: [] } })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.empty').exists()).toBe(true)
    expect(wrapper.find('.empty').text()).toBe('暂无查询记录')
  })

  it('renders query history table with results', async () => {
    mockedGetQueryResults.mockResolvedValueOnce({
      data: {
        results: [
          { standard_number: 'GB/T 1.1-2020', status: '现行', found_name: '标准化工作导则', source_site: 'std_gov' },
          { standard_number: 'GB/T 2.0-2019', status: '废止', found_name: null, source_site: null },
        ],
      },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBe(2)
    expect(rows[0].text()).toContain('GB/T 1.1-2020')
    expect(rows[0].text()).toContain('标准化工作导则')
    expect(rows[1].text()).toContain('-')
  })

  it('displays record count when results present', async () => {
    mockedGetQueryResults.mockResolvedValueOnce({
      data: { results: [{ standard_number: 'XX', status: '现行', found_name: 'A', source_site: 'B' }] },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.text-sm').text()).toBe('共 1 条记录')
  })
})
