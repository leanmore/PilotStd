// Node.js 原生测试环境初始化 — jsdom + 浏览器 API mock
// 必须在所有测试文件之前通过 --import 加载

import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!DOCTYPE html><html><head></head><body></body></html>', {
  url: 'http://localhost:3000',
  pretendToBeVisual: true,
})

// 注入全局 DOM API
globalThis.window = dom.window as unknown as Window & typeof globalThis
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, writable: true, configurable: true })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.HTMLInputElement = dom.window.HTMLInputElement
globalThis.HTMLButtonElement = dom.window.HTMLButtonElement

// 模拟 window.matchMedia — app store 初始化时调用
globalThis.window.matchMedia = ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => {},
})) as unknown as typeof window.matchMedia

// 模拟 IntersectionObserver — PrimeVue 组件可能用到
;(globalThis as any).IntersectionObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// 模拟 requestAnimationFrame
globalThis.requestAnimationFrame = (cb: FrameRequestCallback) => {
  setTimeout(cb, 0)
  return 0
}

// 模拟 localStorage (jsdom 已内置，确保可用)
if (!globalThis.localStorage) {
  const store = new Map<string, string>()
  globalThis.localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => { store.set(k, v) },
    removeItem: (k: string) => { store.delete(k) },
    clear: () => { store.clear() },
    get length() { return store.size },
    key: (i: number) => [...store.keys()][i] ?? null,
  }
}
