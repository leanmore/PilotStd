// TaskHistoryList 直接挂载测试：补 P2-08 的失败/状态分支与交互事件。
// 之前只被 TaskView 以空列表挂载，行覆盖 2/22（9.09%），棘轮保护几乎为零。
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'
import TaskHistoryList from './TaskHistoryList.vue'
import type { TaskRecord } from './types'

function makeI18n(locale: 'zh-CN' | 'en' = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
}

function record(id: string, status: TaskRecord['status']): TaskRecord {
  return {
    id,
    time: `2026-11-14 10:0${id}`,
    path: `/inbox/${id}`,
    scanCount: 10,
    queryFound: 6,
    dlSuccess: 4,
    normCount: 3,
    status,
    steps: [],
  }
}

const ButtonStub = {
  name: 'Button',
  props: ['label', 'severity', 'size', 'text'],
  emits: ['click'],
  template: '<button class="btn" @click="$emit(\'click\')">{{ label }}</button>',
}
const TagStub = {
  name: 'Tag',
  props: ['value', 'severity'],
  template: '<span class="tag" :data-severity="severity">{{ value }}</span>',
}
const DataViewStub = {
  name: 'DataView',
  props: ['value', 'size'],
  template: '<div class="dataview"><slot name="list" :items="value" /></div>',
}
const PaginatorStub = {
  name: 'Paginator',
  props: ['rows', 'rowsPerPageOptions', 'totalRecords'],
  emits: ['page'],
  template: '<button class="paginator" @click="$emit(\'page\', { page: 1, rows: 2 })">page</button>',
}

function mountList(history: TaskRecord[], page = 0, rows = 2, locale: 'zh-CN' | 'en' = 'zh-CN') {
  return mount(TaskHistoryList, {
    props: { history, page, rows },
    global: {
      plugins: [makeI18n(locale)],
      stubs: { Button: ButtonStub, Tag: TagStub, DataView: DataViewStub, Paginator: PaginatorStub },
    },
  })
}

describe('TaskHistoryList', () => {
  it('空历史不渲染卡片', () => {
    const wrapper = mountList([])
    expect(wrapper.find('.card').exists()).toBe(false)
  })

  it('四种状态各自映射 severity 与文案（失败/停止/部分成功都要可见）', () => {
    const wrapper = mountList([record('1', 'success'), record('2', 'partial'), record('3', 'stopped'), record('4', 'fail')], 0, 10)
    const tags = wrapper.findAll('.tag')
    expect(tags).toHaveLength(4)
    expect(tags.map((t) => t.attributes('data-severity'))).toEqual(['success', 'warn', 'warn', 'danger'])
    // 文案走 i18n：失败态不能显示成"成功"
    expect(tags[3].text()).not.toBe(tags[0].text())
  })

  it('按 page/rows 切片：第二页只显示剩余记录', () => {
    const wrapper = mountList([record('1', 'success'), record('2', 'fail'), record('3', 'partial')], 1, 2)
    expect(wrapper.findAll('.btn')).toHaveLength(3) // 只有 1 条记录 × 3 个按钮
  })

  it('详情/重跑/删除分别抛出 view/rerun/delete 事件', async () => {
    const wrapper = mountList([record('1', 'fail')], 0, 10)
    const buttons = wrapper.findAll('.btn')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')
    expect(wrapper.emitted('view')?.[0]?.[0]).toMatchObject({ id: '1' })
    expect(wrapper.emitted('rerun')?.[0]?.[0]).toMatchObject({ id: '1' })
    expect(wrapper.emitted('delete')?.[0]?.[0]).toMatchObject({ id: '1' })
  })

  it('翻页事件透传给父组件', async () => {
    const wrapper = mountList([record('1', 'success')], 0, 10)
    await wrapper.find('.paginator').trigger('click')
    expect(wrapper.emitted('page')?.[0]?.[0]).toMatchObject({ page: 1, rows: 2 })
  })

  it('英文 locale 下状态文案取英文 key', () => {
    const wrapper = mountList([record('1', 'fail')], 0, 10, 'en')
    expect(wrapper.find('.tag').text()).toBe((en as any).task.status.failed)
  })
})
