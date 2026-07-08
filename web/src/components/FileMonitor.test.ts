// components/FileMonitor.test.ts — 文件监控组件测试
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import FileMonitor from './FileMonitor.vue'

// Mock http 请求
const mockGet = vi.fn()
const mockPut = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api/http', () => ({
  default: { get: (...args: any[]) => mockGet(...args), put: (...args: any[]) => mockPut(...args), post: (...args: any[]) => mockPost(...args) },
}))

// PrimeVue 组件在本项目通过 main.ts 的 app.component() 逐个注册，
// 测试中需要 stub 以避免 "Failed to resolve component" 警告。
// Button stub 需要 label 插值以支持文本断言
function mountFileMonitor() {
  return mount(FileMonitor, {
    global: {
      stubs: {
        Button: { template: '<button :disabled="$attrs.disabled" @click="$emit(\'click\')">{{ $attrs.label }}<slot /></button>', inheritAttrs: false },
        InputText: { template: '<input type="text" :value="$attrs.modelValue" />', inheritAttrs: false },
        InputNumber: { template: '<input type="number" />' },
        ToggleSwitch: { template: '<input type="checkbox" :checked="$attrs.modelValue" />', inheritAttrs: false },
        Tag: { template: '<span class="tag-stub"><slot /></span>' },
        Message: { template: '<div class="message-stub"><slot /></div>' },
      },
    },
  })
}

describe('FileMonitor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/monitor/config') {
        return Promise.resolve({ data: { enabled: true, watch_path: '/inbox', delay_seconds: 5, recursive: true, file_patterns: ['.pdf'], ignore_patterns: ['.tmp'], auto_archive: true } })
      }
      if (url === '/monitor/status') {
        return Promise.resolve({ data: { running: true, enabled: true, watch_path: '/inbox', delay_seconds: 5, last_processed: '', processed_today: 0, success_today: 0, failed_today: 0 } })
      }
      if (url === '/monitor/stats') {
        return Promise.resolve({ data: { date: '2026-07-08', processed: 10, success: 8, failed: 2 } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('渲染监控状态栏，显示运行状态信息', async () => {
    const wrapper = mountFileMonitor()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('监控状态')
    expect(html).toContain('监控路径')
  })

  it('渲染启动/停止按钮', async () => {
    const wrapper = mountFileMonitor()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    // 查找所有 button 元素
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThanOrEqual(2)
  })

  it('渲染配置区域：监控开关、路径、延迟等表单项', async () => {
    const wrapper = mountFileMonitor()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('启用文件监控')
    expect(html).toContain('延迟')
    expect(html).toContain('监控子目录')
    expect(html).toContain('自动归档')
  })

  it('配置区域中有保存配置按钮', async () => {
    const wrapper = mountFileMonitor()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('保存配置')
  })

  it('加载失败时组件仍能正常渲染不崩溃', async () => {
    mockGet.mockRejectedValue(new Error('网络错误'))
    const wrapper = mountFileMonitor()

    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('监控状态')
    expect(wrapper.html()).toContain('启用文件监控')
  })
})
