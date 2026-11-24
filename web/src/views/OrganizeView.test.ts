// OrganizeView 测试（文件管理 / 整理）
//
// 契约：挂载按 rootPath 浏览；目录行点击进入子目录并刷新面包屑；
// 分页接收上次页码（Paginator 的 first 必须受控）；清理空目录后重新浏览；
// admin 才能勾选文件并入队时效性检查（提交的是文件绝对路径数组）。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { getFiles, postCleanEmpty } from '@/api'
import { enqueueValidityCheck } from '@/api/validity'
import OrganizeView from './OrganizeView.vue'

const storage = vi.hoisted(() => new Map<string, string>())
const store = vi.hoisted(() => ({ role: 'admin' }))
vi.mock('@/lib/storage', () => ({
  getItem: (k: string) => storage.get(k) ?? null,
  setItem: (k: string, v: string) => void storage.set(k, v),
  removeItem: (k: string) => void storage.delete(k),
}))
vi.mock('@/stores/app', () => ({ useAppStore: () => store }))
vi.mock('@/api', () => ({ getFiles: vi.fn(), postCleanEmpty: vi.fn() }))
vi.mock('@/api/validity', () => ({ enqueueValidityCheck: vi.fn() }))

const FILES = [
  { name: 'GB.pdf', path: '/standards/GB.pdf', type: 'pdf', size: 2048 },
  { name: 'sub', path: '/standards/sub', type: 'dir', size: 0 },
  { name: 'big.pdf', path: '/standards/big.pdf', type: 'pdf', size: 2 * 1048576 },
]
const DataView = { name: 'DataView', props: ['value'], template: '<div class="dv"><slot name="list" :items="value" /></div>' }
const Paginator = { name: 'Paginator', props: ['first', 'rows', 'totalRecords'], emits: ['page'], template: '<div class="pg" />' }
const AppCheckbox = {
  name: 'AppCheckbox', props: ['modelValue'], emits: ['change', 'update:modelValue'],
  template: '<input type="checkbox" class="cb" @change="$emit(\'change\')" />',
}

function mountView() {
  return mount(OrganizeView, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { DataView, Paginator, AppCheckbox, LogBar: true },
    },
  })
}

describe('OrganizeView 文件管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage.clear()
    store.role = 'admin'
    vi.mocked(getFiles).mockResolvedValue({ files: JSON.parse(JSON.stringify(FILES)) } as never)
    vi.mocked(postCleanEmpty).mockResolvedValue({ removed: 3 } as never)
    vi.mocked(enqueueValidityCheck).mockResolvedValue({ ok: true, enqueued: 1, total: 1 } as never)
  })

  it('挂载按默认根路径浏览，并渲染文件行与格式化大小', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getFiles).toHaveBeenCalledWith('/standards', '/organize')
    const text = wrapper.text()
    expect(text).toContain('GB.pdf')
    expect(text).toContain('2 KB')
    expect(text).toContain('2.0 MB')
    expect(text).toContain('3 个文件')
  })

  it('点击目录行进入子目录：重新取数并同步面包屑', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.dir-row').find((r) => r.text().includes('sub'))!.trigger('click')
    await flushPromises()

    expect(getFiles).toHaveBeenLastCalledWith('/standards/sub', '/organize')
    expect(wrapper.text()).toContain('standards')
    expect(wrapper.text()).toContain('sub')
  })

  it('分页：从存储恢复页码后 Paginator.first 受控，翻页写回存储', async () => {
    storage.set('organize_page', '2')
    const wrapper = mountView()
    await flushPromises()

    const pg = wrapper.findComponent({ name: 'Paginator' })
    expect(pg.props('first')).toBe(60) // page 2 * rows 30
    pg.vm.$emit('page', { page: 1 })
    await flushPromises()
    expect(storage.get('organize_page')).toBe('1')
  })

  it('清理空目录：按当前路径调用并展示清理条数，随后刷新列表', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('清理空目录'))!.trigger('click')
    await flushPromises()

    expect(postCleanEmpty).toHaveBeenCalledWith('/standards')
    expect(wrapper.text()).toContain('已清理 3 个空目录')
    expect(getFiles).toHaveBeenCalledTimes(2)
  })

  it('admin 勾选文件后入队：提交的是文件绝对路径数组（不含目录）', async () => {
    const wrapper = mountView()
    await flushPromises()
    // 第 0 个复选框是「全选本页文件」，其后才是文件行
    await wrapper.findAll('.cb')[1].trigger('change')
    expect(wrapper.text()).toContain('已选 1 个文件')

    await wrapper.findAll('button').find((b) => b.text().includes('加入时效性检查'))!.trigger('click')
    await flushPromises()
    expect(enqueueValidityCheck).toHaveBeenCalledWith(['/standards/GB.pdf'])
    expect(wrapper.text()).toContain('已加入队列：1/1')
  })

  it('普通用户看不到全选/勾选与入队入口', async () => {
    store.role = 'user'
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.cb').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('加入时效性检查')
  })

  it('浏览失败时显示后端 error 文案', async () => {
    vi.mocked(getFiles).mockRejectedValue({ response: { data: { error: '路径不存在' } } })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.err-msg').text()).toContain('路径不存在')
  })

  it('清理空目录失败：展示错误提示且不产生未捕获 rejection（2026-11-25 修复）', async () => {
    vi.mocked(postCleanEmpty).mockRejectedValue({ response: { data: { error: '磁盘只读' } } })

    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('清理空目录'))!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('磁盘只读')
    // 失败后不应再触发列表刷新（原实现无论如何都会 browse()）
    expect(getFiles).toHaveBeenCalledTimes(1)
  })
})
