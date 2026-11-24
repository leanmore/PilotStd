// SettingsTabSites 测试（查询站点限额/冷却编辑）
//
// 契约：GET /settings/sites 后把 snake_case 字段映射为驼峰并给默认值；
// 只有 admin 能解锁编辑；保存前 validate 拦截空值/负数/间隔 <0.1，
// 通过后 PUT /settings/sites/<name> 且四个限额字段一一对应；放弃修改需二次确认。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import http from '@/api/http'
import SettingsTabSites from './SettingsTabSites.vue'

const store = vi.hoisted(() => ({ role: 'admin' }))
const notify = vi.hoisted(() => ({
  success: vi.fn(), warn: vi.fn(), error: vi.fn(), info: vi.fn(), removeGroup: vi.fn(),
}))
const confirmRequire = vi.hoisted(() => vi.fn())
vi.mock('@/stores/app', () => ({ useAppStore: () => store }))
vi.mock('@/composables/useAppToast', () => ({ useAppToast: () => notify }))
vi.mock('primevue/useconfirm', () => ({ useConfirm: () => ({ require: confirmRequire }) }))
vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))

// 后端 SiteConfigResponse 的四个限额字段是 camelCase（maxRequests/dailyLimit/...），
// 只有健康检查状态是 snake_case（last_health_check/health_status）。
// 注意：这里刻意用与默认值（600 / 0.5 / null）**不同**的值，否则映射错误会被默认值掩盖。
const SITE = {
  name: 'ahbz', label: '安徽标准', url: 'http://a.example', priority: 1,
  maxRequests: 10, dailyLimit: 100, coolingSeconds: 300, requestInterval: 0.25,
  remainingQuota: 42, coolingRemaining: 7, last_health_check: null, health_status: 'up',
}

function mountTab() {
  const wrapper = mount(SettingsTabSites, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  return wrapper
}

function response(sites: unknown[]) {
  return { data: { sites } } as never
}

describe('SettingsTabSites 站点限额编辑', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.role = 'admin'
    vi.mocked(http.get).mockResolvedValue(response([SITE]))
    vi.mocked(http.put).mockResolvedValue({ data: { ok: true } } as never)
  })

  it('挂载加载站点并渲染后端 camelCase 限额字段', async () => {
    const wrapper = mountTab()
    await flushPromises()

    expect(http.get).toHaveBeenCalledWith('/settings/sites', { routeTag: '/settings' })
    const text = wrapper.text()
    expect(text).toContain('安徽标准')
    expect(text).toContain('#1')
    expect(text).toContain('http://a.example')
    expect(text).toContain('0.3s') // requestInterval=0.25 → toFixed(1)
    const site = (wrapper.vm as unknown as { sites: Record<string, unknown>[] }).sites[0]
    expect(site.maxRequests).toBe(10)
    expect(site.dailyLimit).toBe(100)
    // 回归（2026-11-25）：四个限额字段必须从**后端 camelCase** 读入，不能被默认值覆盖
    expect(site.coolingSeconds).toBe(300)
    expect(site.requestInterval).toBe(0.25)
    expect(site.remainingQuota).toBe(42)
    expect(site.coolingRemaining).toBe(7)
  })

  it('保存时回写真实限额而非默认值（防静默覆盖后端配置）', async () => {
    const wrapper = mountTab()
    await flushPromises()
    // 解锁 → 直接保存（不改任何值）：PUT 必须是后端下发的真实限额，
    // 而不是映射失败时落到默认值 600 / 0.5（那会静默覆盖真实配置）。
    await wrapper.find('.lock-btn').trigger('click')
    await wrapper.find('.lock-btn').trigger('click')
    await flushPromises()

    expect(http.put).toHaveBeenCalledWith('/settings/sites/ahbz', {
      window_limit: 10,
      daily_limit: 100,
      cooling_seconds: 300,
      request_interval: 0.25,
    })
  })

  it('空列表显示占位文案', async () => {
    vi.mocked(http.get).mockResolvedValue(response([]))
    const wrapper = mountTab()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无可用站点')
  })

  it('请求被取消（null）不弹错误；真实失败才 toast「站点列表加载失败」', async () => {
    vi.mocked(http.get).mockResolvedValue(null as never)
    mountTab()
    await flushPromises()
    expect(notify.error).not.toHaveBeenCalled()

    vi.mocked(http.get).mockRejectedValue(new Error('boom'))
    mountTab()
    await flushPromises()
    expect(notify.error).toHaveBeenCalledWith(expect.objectContaining({ summary: '站点列表加载失败' }))
  })

  it('非 admin 不显示解锁按钮，admin 显示', async () => {
    const adminView = mountTab()
    await flushPromises()
    expect(adminView.find('.lock-btn').exists()).toBe(true)

    store.role = 'user'
    const userView = mountTab()
    await flushPromises()
    expect(userView.find('.lock-btn').exists()).toBe(false)
  })

  it('编辑态输入负数 → 保存按钮禁用且 title 给出负数校验提示，不发 PUT', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.find('.lock-btn').trigger('click')
    const vm = wrapper.vm as unknown as { sites: { maxRequests: number }[] }
    vm.sites[0].maxRequests = -1
    await wrapper.vm.$nextTick()

    const lock = wrapper.find('.lock-btn')
    expect(lock.attributes('disabled')).toBeDefined()
    expect(lock.attributes('title')).toContain('不能为负数')
    await lock.trigger('click')
    await flushPromises()
    expect(http.put).not.toHaveBeenCalled()
  })

  it('合法保存：PUT 载荷四字段与界面值一致，并重新加载', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.find('.lock-btn').trigger('click')
    const vm = wrapper.vm as unknown as { sites: { maxRequests: number; dailyLimit: number }[] }
    vm.sites[0].maxRequests = 20
    vm.sites[0].dailyLimit = 200
    await wrapper.vm.$nextTick()
    await wrapper.find('.lock-btn').trigger('click')
    await flushPromises()

    expect(http.put).toHaveBeenCalledWith('/settings/sites/ahbz', {
      window_limit: 20, daily_limit: 200, cooling_seconds: 300, request_interval: 0.25,
    })
    expect(notify.success).toHaveBeenCalled()
    expect(http.get).toHaveBeenCalledTimes(2)
  })

  it('放弃修改需确认，confirm.accept 后才回滚到快照值', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await wrapper.find('.lock-btn').trigger('click')
    const vm = wrapper.vm as unknown as { sites: { maxRequests: number }[] }
    vm.sites[0].maxRequests = 99
    await wrapper.vm.$nextTick()
    await wrapper.find('.discard-btn').trigger('click')

    expect(confirmRequire).toHaveBeenCalledTimes(1)
    ;(confirmRequire.mock.calls[0][0] as { accept: () => void }).accept()
    await flushPromises()
    expect(vm.sites[0].maxRequests).toBe(10)
  })

  it('健康指示灯 class 反映 health_status（up/down/未检查）', async () => {
    const up = mountTab()
    await flushPromises()
    expect(up.find('.health-dot').classes()).toContain('health-up')
  })
})
