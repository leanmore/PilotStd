// SystemLogCard：日志行解析、空态、清理（24h/全部）成功与失败提示、8s 轮询与卸载清理
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import SystemLogCard from './SystemLogCard.vue'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({ get: vi.fn(), delete: vi.fn() }))
vi.mock('@/api/http', () => ({ default: { get: mocks.get, delete: mocks.delete } }))

function mountCard() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  return mount(SystemLogCard, { global: { plugins: [i18n] } })
}

describe('SystemLogCard', () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue({ data: { logs: [] } })
    mocks.delete.mockReset().mockResolvedValue({ data: { deleted: 5 } })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('无日志：显示"等待日志..."，副标题行数为 0', async () => {
    const w = mountCard()
    await flushPromises()

    expect(mocks.get).toHaveBeenCalledWith('/logs', { params: { tail: 30 }, routeTag: '/' })
    expect(w.find('.empty').text()).toBe('等待日志...')
    expect(w.find('.header-sub').text()).toBe('0 行 · 8s 刷新')
  })

  it('标准行按"时间 [级别] 模块 消息"解析出图标与各字段，非标准行整行兜底', async () => {
    mocks.get.mockResolvedValueOnce({
      data: { logs: ['03-01 12:00:00 [WARN] parser 解析超时', '纯文本一行'] },
    })
    const w = mountCard()
    await flushPromises()

    const lines = w.findAll('.line')
    expect(lines).toHaveLength(2)
    expect(lines[0].find('.lt').text()).toBe('03-01 12:00:00')
    expect(lines[0].find('.lm').text()).toBe('解析超时')
    expect(lines[0].find('.li').classes()).toContain('lv-warn')
    // 非标准行：时间空、级别 info、消息为原文
    expect(lines[1].find('.lt').text()).toBe('')
    expect(lines[1].find('.lm').text()).toBe('纯文本一行')
    expect(lines[1].find('.li').classes()).toContain('lv-info')
  })

  it('清理 24h 前日志：DELETE 带 before_hours=24，提示删除条数并在 3s 后消失', async () => {
    vi.useFakeTimers()
    const w = mountCard()
    await flushPromises()

    const btn = w.findAll('.app-btn').find((b) => b.text().includes('清理旧日志'))!
    await btn.trigger('click')
    await flushPromises()

    expect(mocks.delete).toHaveBeenCalledWith('/admin/logs', { params: { before_hours: 24 } })
    expect(w.find('.clear-msg').text()).toBe('已清理 5 条日志（24h 前）')
    expect(mocks.get).toHaveBeenCalledTimes(2) // 清理后立即刷新

    await vi.advanceTimersByTimeAsync(3000)
    expect(w.find('.clear-msg').exists()).toBe(false)
  })

  it('清空全部日志：before_hours=0，提示"全部日志"', async () => {
    const w = mountCard()
    await flushPromises()

    const btn = w.findAll('.app-btn').find((b) => b.text().includes('清空'))!
    await btn.trigger('click')
    await flushPromises()

    expect(mocks.delete).toHaveBeenCalledWith('/admin/logs', { params: { before_hours: 0 } })
    expect(w.find('.clear-msg').text()).toBe('已清空全部日志（5 条）')
  })

  it('清理失败：提示错误并以 error 样式标记，不触发刷新', async () => {
    mocks.delete.mockRejectedValueOnce(new Error('403'))
    const w = mountCard()
    await flushPromises()
    const before = mocks.get.mock.calls.length

    const btn = w.findAll('.app-btn').find((b) => b.text().includes('清理旧日志'))!
    await btn.trigger('click')
    await flushPromises()

    expect(w.find('.clear-msg').text()).toBe('清理日志失败')
    expect(w.find('.clear-msg').classes()).toContain('error')
    expect(mocks.get).toHaveBeenCalledTimes(before)
  })

  it('每 8s 自动刷新；卸载后定时器停止（无泄漏）', async () => {
    vi.useFakeTimers()
    const w = mountCard()
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(8000)
    expect(mocks.get).toHaveBeenCalledTimes(2)

    w.unmount()
    await vi.advanceTimersByTimeAsync(16000)
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })
})
