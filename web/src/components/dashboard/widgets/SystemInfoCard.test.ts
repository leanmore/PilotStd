// SystemInfoCard：版本号/标准总数/数据库与适配器健康度 —— 骨架、正常、空库、异常计数为 0
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import SystemInfoCard from './SystemInfoCard.vue'
import { getStats } from '@/api'
import http from '@/api/http'
import AppLoading from '@/components/ui/AppLoading.vue'
import zhCN from '@/locales/zh-CN.json'

vi.mock('@/api', () => ({ getStats: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: vi.fn() } }))

const STATS = { current: 10, expired: 2, pending: 3, upcoming: 5 }

function mockAll(version: string | null = '0.55.33', adapters: unknown[] = [{ name: 'a' }, { name: 'b' }]) {
  vi.mocked(http.get).mockImplementation(async (url: string) => ({
    data: url.includes('/version') ? { version } : { adapters },
  }))
  vi.mocked(getStats).mockResolvedValue(STATS)
}

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(SystemInfoCard, { global: { plugins: [i18n] } })
}

describe('SystemInfoCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('并行拉取中先显示骨架，完成后骨架消失', async () => {
    mockAll()
    const w = mountCard()
    expect(w.findComponent(AppLoading).exists()).toBe(true)

    await flushPromises()
    expect(w.findComponent(AppLoading).exists()).toBe(false)
    expect(w.find('.body').exists()).toBe(true)
  })

  it('成功：版本号、标准总数（四态求和）、数据库正常、适配器在线数', async () => {
    mockAll()
    const w = mountCard()
    await flushPromises()

    expect(w.find('.version-val').text()).toBe('v0.55.33')
    expect(w.text()).toContain('20 条')
    expect(w.text()).toContain('2 在线')
    const statuses = w.findAll('.metric-status').map((n) => n.text())
    expect(statuses).toEqual(['正常', '20 条', '2 在线'])
    expect(w.findAll('.metric-fill').every((f) => f.classes().includes('bar-ok'))).toBe(true)
  })

  it('空库：标准总数为 0 时数据库显示"空库"并用 warn 色', async () => {
    vi.mocked(getStats).mockResolvedValue({ current: 0, expired: 0, pending: 0, upcoming: 0 })
    vi.mocked(http.get).mockImplementation(async (url: string) => ({
      data: url.includes('/version') ? { version: '1.0.0' } : { adapters: [] },
    }))
    const w = mountCard()
    await flushPromises()

    expect(w.findAll('.metric-status')[0].text()).toBe('空库')
    expect(w.findAll('.metric-fill')[0].classes()).toContain('bar-warn')
    expect(w.findAll('.metric-status')[2].text()).toBe('0 在线')
    expect(w.find('.version-val').text()).toBe('v1.0.0')
  })

  it('接口无 version 时回退 "—"，不显示 vundefined', async () => {
    mockAll(null)
    const w = mountCard()
    await flushPromises()
    expect(w.find('.version-val').text()).toBe('v—')
  })

  it('请求严格带上路由标记与 type=query 参数', async () => {
    mockAll()
    const w = mountCard()
    await flushPromises()

    expect(getStats).toHaveBeenCalledWith('/')
    expect(http.get).toHaveBeenCalledWith('/system/version', { routeTag: '/' })
    expect(http.get).toHaveBeenCalledWith('/adapter/status', { params: { type: 'query' }, routeTag: '/' })
    expect(w).toBeTruthy()
  })

  it('接口失败：显示「加载失败」，不得把故障渲染成"版本 v / 空库"（D-2 回归）', async () => {
    vi.mocked(http.get).mockRejectedValue(new Error('500'))
    const w = mountCard()
    await flushPromises()

    expect(w.text()).toContain('加载失败')
    expect(w.text()).not.toContain('空库')
  })
})
