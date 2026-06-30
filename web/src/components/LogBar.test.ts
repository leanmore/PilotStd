// components/LogBar.test.ts — 日志栏组件测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LogBar from './LogBar.vue'

// Mock axios 请求
const mockGet = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...args: any[]) => mockGet(...args) },
}))

function mountLogBar(props?: { refreshKey?: number }) {
  return mount(LogBar, { props })
}

// 等待异步更新：使用真实 setTimeout 而非 fake timers
// (LogBar 内部使用 requestAnimationFrame + setInterval，fake timers 会导致死循环)
const waitForAsync = () => new Promise(r => setTimeout(r, 50))

describe('LogBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染日志头部，显示行数', async () => {
    mockGet.mockResolvedValue({ data: { lines: ['[I] 服务启动', '[W] 配额警告'] } })
    const wrapper = mountLogBar()

    await waitForAsync()
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('日志')
    expect(wrapper.html()).toContain('2 行')
    expect(wrapper.text()).toContain('[I] 服务启动')
    expect(wrapper.text()).toContain('[W] 配额警告')
  })

  it('点击头部收起/展开切换', async () => {
    mockGet.mockResolvedValue({ data: { lines: ['test'] } })
    const wrapper = mountLogBar()

    await waitForAsync()
    await wrapper.vm.$nextTick()

    // 初始展开
    expect(wrapper.classes()).not.toContain('collapsed')

    // 点击收起
    const header = wrapper.find('.log-header')
    await header.trigger('click')
    expect(wrapper.classes()).toContain('collapsed')

    // 再次点击展开
    await header.trigger('click')
    expect(wrapper.classes()).not.toContain('collapsed')
  })

  it('refreshKey 变化时重新获取日志', async () => {
    mockGet.mockResolvedValue({ data: { lines: ['first'] } })
    const wrapper = mountLogBar({ refreshKey: 0 })

    await waitForAsync()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('first')

    mockGet.mockResolvedValue({ data: { lines: ['second'] } })
    await wrapper.setProps({ refreshKey: 1 })
    await waitForAsync()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('second')
  })

  it('请求失败时显示错误状态', async () => {
    mockGet.mockRejectedValue(new Error('连接失败'))
    const wrapper = mountLogBar()

    await waitForAsync()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('日志加载失败')
  })

  it('空日志时显示"暂无日志"', async () => {
    mockGet.mockResolvedValue({ data: { lines: [] } })
    const wrapper = mountLogBar()

    await waitForAsync()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('暂无日志')
  })
})
