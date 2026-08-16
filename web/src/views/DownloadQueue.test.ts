import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import DownloadQueue from './DownloadQueue.vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { getTasks } from '@/api/tasks'

vi.mock('@/api/tasks', () => ({
  getTasks: vi.fn(),
}))
const mockedGetTasks = vi.mocked(getTasks)

// stub 外层 Card，透传 content 插槽，让内部 table 可断言
const StubCard = {
  name: 'Card',
  template: '<div class="card-stub"><slot name="content" /></div>',
}

function mountComponent() {
  return shallowMount(DownloadQueue, {
    global: {
      stubs: {
        Card: StubCard,
        Button,
        Tag,
      },
    },
  })
}

describe('DownloadQueue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title 下载队列', () => {
    const wrapper = mountComponent()
    expect(wrapper.find('.page-title').text()).toBe('下载队列')
  })

  it('shows empty state when no tasks and not loading', async () => {
    mockedGetTasks.mockResolvedValueOnce({ data: { items: [] } })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.empty').exists()).toBe(true)
    expect(wrapper.find('.empty').text()).toBe('暂无队列任务')
  })

  it('renders task table rows when API returns tasks', async () => {
    mockedGetTasks.mockResolvedValueOnce({
      data: {
        items: [
          { task_id: 'task-1', task_type: 'download', status: 'running', total_items: 5, created_at: '2026-06-01T10:00:00Z' },
          { task_id: 'task-2', task_type: 'batch', status: 'completed', total_items: 12, created_at: '2026-06-02T08:30:00Z' },
        ],
      },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBe(2)
    expect(rows[0].text()).toContain('task-1')
    expect(rows[1].text()).toContain('task-2')
  })

  it('shows total task count when tasks present', async () => {
    mockedGetTasks.mockResolvedValueOnce({
      data: { items: [{ task_id: 'a', task_type: 'x', status: 'running', total_items: 1, created_at: '2026-06-01T00:00:00Z' }] },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.find('.text-sm').text()).toBe('共 1 个任务')
  })
})
