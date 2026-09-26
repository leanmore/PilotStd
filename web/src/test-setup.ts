// 测试环境全局 Mock — jsdom 不具备 matchMedia、IntersectionObserver 等浏览器 API
import { afterAll, vi } from 'vitest'

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

// 模拟 ResizeObserver —— PrimeVue 4 的 TabList 用它绘制激活条（jsdom 无此 API，
// 缺失时会在下一个宏任务里抛 ReferenceError，导致整个测试文件失败）。
// 必须用 class 而非 vi.fn()：组件里是 `new ResizeObserver(...)`，箭头函数不可构造。
class ResizeObserverStub {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverStub,
})

// ══════════════════════════════════════════════════════════════════════════
// 遗留定时器治理：修掉 PrimeVue TabList ink-bar 定时器跨越 teardown 的竞态
// ══════════════════════════════════════════════════════════════════════════
// 缺陷链路（2026-09-26 定位）：
//   1. `primevue/tablist/index.mjs:48-53` 在 `mounted()` 里排了
//      `setTimeout(() => { updateInkBar(); bindInkBarObserver() }, 150)`，
//      **不保存句柄、`unmounted` 也不清理**；
//   2. `updateInkBar()`（同文件 `:132`）经 `@primeuix/utils` 的
//      `t instanceof HTMLElement` 取宽度（`dist/dom/index.mjs`）；
//   3. 若测试文件在 150ms 内结束，vitest 先摘掉 jsdom 全局再执行该回调
//      → `ReferenceError: HTMLElement is not defined`（unhandled error →
//      CI 报 `Errors 1 error`、exit 1，而 `Tests 230 passed` 掩盖了它）。
//
// 修法：在 setup 层接管 `setTimeout`，登记**尚未触发**的句柄，文件级 `afterAll`
// 一次性 clear 掉，然后还原真实实现。回调根本不会执行 → 既不需要 fake timers
// （会扭曲微任务时序），也不需要 sleep。
//
// 被否掉的两个候选（均实测有害/无效，见技术债记录与提交说明）：
//   候选 1 `Object.defineProperty(globalThis,'HTMLElement',{configurable:false})`
//     → vitest teardown 用 `delete` 摘全局，实测全量套件报
//       `TypeError: Cannot delete property 'HTMLElement' of #<Object>`（34 errors）；
//   候选 2 `afterEach` 里补回 `HTMLElement`
//     → 全局是在 afterEach **之后**的 teardown 阶段被摘掉的，补不回来。
//   另外禁止用空壳类 `class HTMLElement {}` 兜底：`instanceof` 会恒为 false，
//   让 `getOuterWidth` 静默返回 0（比 ReferenceError 更隐蔽）。
type TimerHandle = ReturnType<typeof globalThis.setTimeout>
const realSetTimeout = globalThis.setTimeout
const pendingTimers = new Set<TimerHandle>()

globalThis.setTimeout = ((handler: unknown, timeout?: number, ...args: unknown[]) => {
  const id = realSetTimeout((...cbArgs: unknown[]) => {
    pendingTimers.delete(id)
    if (typeof handler === 'function') (handler as (...a: unknown[]) => void)(...cbArgs)
  }, timeout, ...args)
  pendingTimers.add(id)
  return id
}) as typeof globalThis.setTimeout

/** 未触发（仍排队）的真实定时器数量——供回归测试观测 PrimeVue 的 ink-bar 定时器。 */
export function pendingTimerCount(): number {
  return pendingTimers.size
}

/** 清掉本文件内仍排队的真实定时器（setup 的 afterAll 调它；测试也可直接调用于断言）。 */
export function clearPendingTimers(): void {
  for (const id of pendingTimers) clearTimeout(id)
  pendingTimers.clear()
}

afterAll(() => {
  clearPendingTimers()
  globalThis.setTimeout = realSetTimeout
})

