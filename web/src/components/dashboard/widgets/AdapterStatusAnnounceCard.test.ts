// AdapterStatusAnnounceCard：公告适配器状态行 —— 名称映射、健康检查文案/圆点、冷却与冻结倒计时、
// 失败详情 tooltip、加载失败提示、卸载清理定时器
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AdapterStatusAnnounceCard from './AdapterStatusAnnounceCard.vue'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: mocks.get } }))

function adapter(over: Record<string, unknown> = {}) {
  return {
    name: 'gb', status: 'normal', frozen_until: null, remaining_seconds: 0,
    freeze_count: 0, fail_streak: 0, last_health_check: null, health_status: null,
    ...over,
  }
}

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(AdapterStatusAnnounceCard, { global: { plugins: [i18n] } })
}

describe('AdapterStatusAnnounceCard', () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue({ data: { adapters: [] } })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.useRealTimers()
  })

  it('无数据：显示通用空态；请求带 type=announcement 与路由标记', async () => {
    const w = mountCard()
    await flushPromises()

    expect(mocks.get).toHaveBeenCalledWith('/adapter/status', { params: { type: 'announcement' }, routeTag: '/' })
    expect(w.find('.empty').text()).toBe('暂无数据')
  })

  it('名称映射与状态：gb 显示中文全称，normal/cooldown/frozen 各显示对应文案', async () => {
    vi.useFakeTimers() // 冷却倒计时每秒改写 remaining_seconds，固定时钟保证断言稳定
    mocks.get.mockResolvedValueOnce({
      data: {
        adapters: [
          adapter({ name: 'gb', status: 'normal' }),
          adapter({ name: 'hb', status: 'cooldown', remaining_seconds: 30 }),
          adapter({ name: 'db', status: 'frozen', remaining_seconds: 60 }),
          adapter({ name: 'x', status: 'normal' }),
        ],
      },
    })
    const w = mountCard()
    await flushPromises()

    const rows = w.findAll('.row')
    expect(rows).toHaveLength(4)
    expect(rows[0].text()).toContain('国家标准公告')
    expect(rows[0].text()).toContain('正常')
    expect(rows[1].text()).toContain('冷却 30s')
    expect(rows[2].text()).toContain('冻结 60s')
    expect(rows[3].find('.row-name').text()).toBe('X') // 未映射名称回退大写
    // 行状态 class 用于边框/底色语义
    expect(rows[1].classes()).toContain('cooldown')
    expect(rows[2].classes()).toContain('frozen')
  })

  it('健康检查：未检查/分钟/小时三段文案，圆点颜色随 health_status 变化', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-01T12:00:00'))
    mocks.get.mockResolvedValueOnce({
      data: {
        adapters: [
          adapter({ name: 'gb', last_health_check: null, health_status: 'up' }),
          adapter({ name: 'hb', last_health_check: '2026-03-01T11:30:00', health_status: 'down' }),
          adapter({ name: 'db', last_health_check: '2026-03-01T10:00:00' }),
        ],
      },
    })
    const w = mountCard()
    await flushPromises()

    const rows = w.findAll('.row')
    expect(rows[0].find('.health-time').text()).toBe('尚未检查')
    expect(rows[0].find('.health-dot').classes()).toContain('health-up')
    expect(rows[1].find('.health-time').text()).toBe('最后检查：30 分钟前')
    expect(rows[1].find('.health-dot').classes()).toContain('health-down')
    expect(rows[2].find('.health-time').text()).toBe('最后检查：2 小时前')
    expect(rows[2].find('.health-dot').classes()).toContain('health-none')
  })

  it('fail_streak>0 时显示警告图标，title 汇总冻结/连续失败次数', async () => {
    mocks.get.mockResolvedValueOnce({
      data: { adapters: [adapter({ fail_streak: 4, freeze_count: 2 })] },
    })
    const w = mountCard()
    await flushPromises()

    const warn = w.find('.row-warn')
    expect(warn.exists()).toBe(true)
    expect(warn.attributes('title')).toBe('冻结2次 / 连续失败4次')
  })

  it('拉取失败：显示加载失败错误', async () => {
    mocks.get.mockRejectedValueOnce(new Error('500'))
    const w = mountCard()
    await flushPromises()
    expect(w.find('.err').text()).toBe('加载失败')
  })

  it('冷却倒计时每秒递减；卸载后停止（不再轮询/倒计时）', async () => {
    vi.useFakeTimers()
    mocks.get.mockResolvedValue({ data: { adapters: [adapter({ status: 'cooldown', remaining_seconds: 3 })] } })
    const w = mountCard()
    await flushPromises()
    expect(w.find('.row').text()).toContain('冷却 3s')

    await vi.advanceTimersByTimeAsync(1000)
    await w.vm.$nextTick()
    expect(w.find('.row').text()).toContain('冷却 2s')

    w.unmount()
    const calls = mocks.get.mock.calls.length
    await vi.advanceTimersByTimeAsync(3000)
    expect(mocks.get).toHaveBeenCalledTimes(calls)
  })
})
