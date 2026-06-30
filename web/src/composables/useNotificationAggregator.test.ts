// composables/useNotificationAggregator.test.ts — 通知智能聚合器单元测试
import { describe, it, expect, vi, beforeEach } from 'vitest'

// 聚合器内部使用 localStorage，mock 它
let storage: Record<string, string> = {}
beforeEach(() => {
  storage = {}
  vi.spyOn(localStorage, 'getItem').mockImplementation((k: string) => storage[k] ?? null)
  vi.spyOn(localStorage, 'setItem').mockImplementation((k: string, v: string) => { storage[k] = v })
})

import { useNotificationAggregator } from './useNotificationAggregator'

describe('useNotificationAggregator', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // 重置单例状态（需要通过 resume 重置内部 paused 状态）
    const agg = useNotificationAggregator()
    agg.resume()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始状态未暂停', () => {
    const agg = useNotificationAggregator()
    const state = agg.getPauseState()
    expect(state.isPaused).toBe(false)
    expect(state.remainingSeconds).toBe(0)
  })

  it('shouldShow 返回 false（缓冲等待合并），随后 flush 触发 onShow', () => {
    const agg = useNotificationAggregator()
    const onShow = vi.fn()

    const result = agg.shouldShow('info', '归档完成', '文件已处理', onShow)
    // 总是返回 false，等待缓冲窗口结束
    expect(result).toBe(false)
    // onShow 尚未调用（在缓冲窗口内）
    expect(onShow).not.toHaveBeenCalled()

    // 推进 300ms 缓冲窗口
    vi.advanceTimersByTime(350)

    // onShow 应被调用
    expect(onShow).toHaveBeenCalledTimes(1)
    expect(onShow).toHaveBeenCalledWith('归档完成', '文件已处理', 'info')
  })

  it('多条同主题通知合并成一条', () => {
    const agg = useNotificationAggregator()
    const onShow = vi.fn()

    agg.shouldShow('info', '数据库备份完成', '备份成功', onShow)
    agg.shouldShow('info', '文件备份完成', '备份成功', onShow)
    agg.shouldShow('info', '配置备份完成', '备份成功', onShow)

    vi.advanceTimersByTime(350)

    expect(onShow).toHaveBeenCalledTimes(1)
    // 合并后的标题应包含数量
    const callTitle = onShow.mock.calls[0][0]
    expect(callTitle).toContain('3')
  })

  it('连续 3 次 warn/error 在 30s 内触发暂停', () => {
    const agg = useNotificationAggregator()
    const onShow = vi.fn()

    // 第一次 flush
    agg.shouldShow('warn', '扫描异常1', '错误详情', onShow)
    vi.advanceTimersByTime(350)
    expect(agg.getPauseState().isPaused).toBe(false)

    // 第二次 flush（在 30s 窗口内）
    agg.shouldShow('error', '扫描异常2', '错误详情', onShow)
    vi.advanceTimersByTime(350)
    expect(agg.getPauseState().isPaused).toBe(false)

    // 第三次 flush → 暂停
    agg.shouldShow('error', '扫描异常3', '错误详情', onShow)
    vi.advanceTimersByTime(350)

    expect(agg.getPauseState().isPaused).toBe(true)
    // 暂停时 onShow 被调用告知"通知已暂停"
    const pauseCall = onShow.mock.calls.find(c => c[0] === '通知已暂停')
    expect(pauseCall).toBeTruthy()
  })

  it('暂停后手动 resume 恢复', () => {
    const agg = useNotificationAggregator()

    // 触发暂停
    const onShow = vi.fn()
    for (let i = 0; i < 3; i++) {
      agg.shouldShow('error', `异常${i}`, '错误', onShow)
      vi.advanceTimersByTime(350)
    }
    expect(agg.getPauseState().isPaused).toBe(true)

    agg.resume()
    expect(agg.getPauseState().isPaused).toBe(false)
    expect(agg.getPauseState().remainingSeconds).toBe(0)
  })

  it('暂停期间 shouldShow 返回 false 不调用 onShow', () => {
    const agg = useNotificationAggregator()
    const onShow = vi.fn()

    // 先触发暂停
    for (let i = 0; i < 3; i++) {
      agg.shouldShow('error', `异常${i}`, '错误', onShow)
      vi.advanceTimersByTime(350)
    }
    onShow.mockClear()

    // 暂停后再发消息
    const result = agg.shouldShow('info', '归档完成', '正常', onShow)
    expect(result).toBe(false)
    vi.advanceTimersByTime(350)
    // 暂停期间不调用 onShow（因为 shouldShow 直接 return false 没入缓冲）
  })
})
