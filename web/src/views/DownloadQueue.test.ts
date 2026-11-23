import { describe, it, expect, vi, beforeEach } from 'vitest'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
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

/**
 * AppTable 的浅挂载替身：真实 AppTable 内部是 PrimeVue DataTable，
 * shallowMount 会把整棵子树 stub 掉（连 tbody 都不渲染），
 * 「行数 / 单元格文案」类断言就全部失效。
 * 这里还原最小可断言结构：按 value 逐行输出六个字段（与模板 Column 顺序一致）。
 */
const StubAppTable = {
  name: 'AppTable',
  props: ['value'],
  template: `<table class="data-table-stub">
    <thead><tr><th>任务</th><th>类型</th><th>状态</th><th>条目</th><th>创建</th><th>操作</th></tr></thead>
    <tbody>
      <tr v-for="(row, i) in (value || [])" :key="i">
        <td>{{ row.task_id }}</td>
        <td>{{ row.task_type }}</td>
        <td>{{ row.status }}</td>
        <td>{{ row.total_items }}</td>
        <td>{{ new Date(row.created_at).toLocaleString('zh-CN') }}</td>
        <td><slot name="cell-action" :data="row" /></td>
      </tr>
    </tbody>
  </table>`,
}

function makeI18n(locale: 'zh-CN' | 'en') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
}

function mountComponent(locale: 'zh-CN' | 'en' = 'zh-CN') {
  return shallowMount(DownloadQueue, {
    global: {
      plugins: [makeI18n(locale)],
      stubs: {
        Card: StubCard,
        Button,
        Tag,
        AppTable: StubAppTable,
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

  it('切换语言到 en 后文案随之变化（i18n 生效）', async () => {
    const zh = mountComponent('zh-CN')
    await nextTick()
    expect(zh.find('.page-title').text()).toBe('下载队列')

    const english = mountComponent('en')
    await nextTick()
    expect(english.find('.page-title').text()).toBe('Download Queue')
  })
})
