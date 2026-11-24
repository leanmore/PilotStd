// QuickActionsCard：路由 meta 驱动的快捷操作（排序/权限/兜底）、导航跳转、动作型扫描链路
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import QuickActionsCard from './QuickActionsCard.vue'
import { useAppStore } from '@/stores/app'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { post: mocks.post } }))

const Dummy = { template: '<div />' }
const ROUTES = [
  { path: '/', component: Dummy },
  { path: '/task', component: Dummy, meta: { showInQuickActions: true, titleKey: 'nav.task', quickActionOrder: 3, icon: 'pi pi-play' } },
  { path: '/pending', component: Dummy, meta: { showInQuickActions: true, titleKey: 'nav.pending', quickActionOrder: 1 } },
  { path: '/settings', component: Dummy, meta: { showInQuickActions: true, title: '设置页', permission: 'admin', quickActionOrder: 2 } },
  { path: '/__action/scan', component: Dummy, meta: { showInQuickActions: true, titleKey: 'dashboard.quick_actions.action_scan', quickActionOrder: 4, quickActionType: 'action', handler: 'scanAndIndex' } },
]
/** 无任何 showInQuickActions 标记：触发组件内置兜底 */
const NO_META_ROUTES = [{ path: '/', component: Dummy }]

async function mountCard(role = 'user', routeDefs: typeof ROUTES = ROUTES) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAppStore().role = role
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const router = createRouter({ history: createMemoryHistory(), routes: routeDefs })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(QuickActionsCard, { global: { plugins: [pinia, router, i18n] } })
  const items = () => wrapper.findAll('[data-testid="quick-action-item"]')
  return { wrapper, router, items }
}

describe('QuickActionsCard', () => {
  beforeEach(() => {
    mocks.post.mockReset()
  })

  it('没有任何路由标记时使用内置 5 项兜底', async () => {
    const { items } = await mountCard('user', NO_META_ROUTES)
    expect(items()).toHaveLength(5)
    expect(items().map((i) => i.find('.label').text())).toEqual(['任务', '整理', '待处理', '公告', '扫描入库'])
  })

  it('按 quickActionOrder 排序，并按 permission 过滤不可见项', async () => {
    const { items } = await mountCard('user')
    expect(items().map((i) => i.find('.label').text())).toEqual(['待处理', '任务', '扫描入库'])

    const { items: adminItems } = await mountCard('admin')
    expect(adminItems().map((i) => i.find('.label').text())).toEqual(['待处理', '设置页', '任务', '扫描入库'])
  })

  it('点击导航型操作：调用 router.push 到目标路径', async () => {
    const { router, items } = await mountCard()
    const pushSpy = vi.spyOn(router, 'push')
    await items()[1].trigger('click') // index0=待处理，index1=/task
    expect(pushSpy).toHaveBeenCalledWith('/task')
  })

  it('点击动作型操作：POST /scan-and-index 并显示入库条数', async () => {
    mocks.post.mockResolvedValueOnce({ data: { indexed: 3 } })
    const { wrapper, items } = await mountCard()
    await items()[2].trigger('click')
    await flushPromises()

    expect(mocks.post).toHaveBeenCalledWith('/scan-and-index')
    expect(wrapper.find('.scan-msg').text()).toBe('扫描完成，入库 3 条标准')
    expect(wrapper.find('.scan-msg').classes()).not.toContain('error')
  })

  it('扫描进行中：按钮进入 disabled 态且文案变为"扫描中…"', async () => {
    let resolveScan!: (value: { data: unknown }) => void
    const pending = new Promise<{ data: unknown }>((resolve) => { resolveScan = resolve })
    mocks.post.mockReturnValueOnce(pending)
    const { items } = await mountCard()
    await items()[2].trigger('click')

    expect(items()[2].classes()).toContain('disabled')
    expect(items()[2].text()).toContain('扫描中…')

    resolveScan({ data: { indexed: 0 } })
    await flushPromises()
    expect(items()[2].classes()).not.toContain('disabled')
  })

  it('扫描失败：优先显示后端 error，无 error 时回退 i18n 文案并标红', async () => {
    const { wrapper, items } = await mountCard()

    mocks.post.mockRejectedValueOnce({ response: { data: { error: '权限不足' } } })
    await items()[2].trigger('click')
    await flushPromises()
    expect(wrapper.find('.scan-msg').text()).toBe('权限不足')
    expect(wrapper.find('.scan-msg').classes()).toContain('error')

    mocks.post.mockRejectedValueOnce(new Error('network down'))
    await items()[2].trigger('click')
    await flushPromises()
    expect(wrapper.find('.scan-msg').text()).toBe('扫描失败')
  })

  it('path 以 /__action/ 开头的动作项不导航（to 被置空）', async () => {
    const { router, items } = await mountCard()
    const pushSpy = vi.spyOn(router, 'push')
    mocks.post.mockResolvedValueOnce({ data: { indexed: 1 } })
    await items()[2].trigger('click')
    await flushPromises()
    expect(pushSpy).not.toHaveBeenCalled()
  })
})
