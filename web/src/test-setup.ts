// 测试环境全局 Mock — jsdom 不具备 matchMedia、IntersectionObserver 等浏览器 API
import { vi } from 'vitest'

// 模拟 window.matchMedia —— app store 初始化时调用
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// 模拟 IntersectionObserver —— PrimeVue 组件可能用到
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  })),
})

// 模拟 requestAnimationFrame
window.requestAnimationFrame = vi.fn().mockImplementation((cb: FrameRequestCallback) => {
  setTimeout(cb, 0)
  return 0
}) as unknown as typeof window.requestAnimationFrame
