// web/src/composables/useIncrementalScroll.test.ts
// 覆盖 IntersectionObserver 哨兵加载方案：
//   - Observer 生命周期（创建/observe/unobserve/disconnect）
//   - 哨兵可见触发追加（50 条/批）
//   - 上限 300 条后的"加载剩余"按钮
//   - 全部显示后停止观察
// 说明：文件名遵循项目 vitest 约定（include: src/**/*.test.ts），
//       任务指令中的 .spec.ts 后缀不会被现有 vitest 配置匹配。

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, nextTick, ref, type Ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useIncrementalScroll } from './useIncrementalScroll'

// ── IntersectionObserver mock ─────────────────────────────────────────
// jsdom 无原生实现，test-setup.ts 已装一个空 mock；这里覆盖为"可手动触发回调"的版本，
// 并在 afterEach 恢复 test-setup 的 mock，防止污染其他测试。
const setupIO = (globalThis as any).IntersectionObserver

const ioMock = vi.hoisted(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  callback: null as ((entries: any[], observer: any) => void) | null,
  instance: null as any,
  createdRootMargin: '',
}))

beforeEach(() => {
  ioMock.observe.mockClear()
  ioMock.unobserve.mockClear()
  ioMock.disconnect.mockClear()
  ioMock.callback = null
  ioMock.instance = null
  ioMock.createdRootMargin = ''
  ;(globalThis as any).IntersectionObserver = vi.fn(function (this: any, cb: any, opts?: any) {
    // 必须用 function 而非箭头函数：vitest 4 的 vi.fn 箭头实现无法被 new 调用
    ioMock.createdRootMargin = opts?.rootMargin ?? ''
    ioMock.callback = cb
    ioMock.instance = {
      observe: ioMock.observe,
      unobserve: ioMock.unobserve,
      disconnect: ioMock.disconnect,
      root: opts?.root ?? null,
      rootMargin: opts?.rootMargin ?? '0px',
      thresholds: Array.isArray(opts?.threshold) ? opts.threshold : [opts?.threshold ?? 0],
      takeRecords: () => [],
    }
    return ioMock.instance
  })
})

afterEach(() => {
  ;(globalThis as any).IntersectionObserver = setupIO
  vi.restoreAllMocks()
})

/** 手动触发 IntersectionObserver 回调，模拟哨兵元素进入/离开视口 */
function triggerIntersect(isIntersecting: boolean) {
  expect(ioMock.callback).not.toBeNull()
  ioMock.callback!([{ isIntersecting, target: ioMock.instance }], ioMock.instance)
}

function makeRecords(count: number) {
  return Array.from({ length: count }, (_, i) => ({ id: i + 1, name: `n${i}` }))
}

// 宿主组件：与真实调用方一致 —— 调用方持有 sentinel ref，模板内真实渲染哨兵 div
const Host = defineComponent({
  props: { count: { type: Number, required: true } },
  setup(props) {
    const records = ref<any[]>(makeRecords(props.count))
    const sentinel = ref<HTMLElement | null>(null)
    const sc = useIncrementalScroll(records, sentinel)
    return { sc, records, sentinel }
  },
  template: '<div><div ref="sentinel" class="scroll-sentinel" style="height:1px" /></div>',
})

async function mountHost(count: number) {
  const wrapper = mount(Host, { props: { count } })
  await flushPromises()
  await nextTick()
  await nextTick()
  return wrapper as any
}

describe('useIncrementalScroll（IntersectionObserver 方案）', () => {
  it('哨兵元素挂载后创建 IntersectionObserver 并 observe（含提前 100px rootMargin）', async () => {
    await mountHost(120)
    expect(ioMock.createdRootMargin).toContain('100px')
    expect(ioMock.observe).toHaveBeenCalledTimes(1)
    expect(ioMock.observe).toHaveBeenCalledWith(expect.any(HTMLElement))
  })

  it('哨兵可见时触发追加：120 条 → 首屏 50 → 触发 → 100 → 再触发 → 120', async () => {
    const wrapper = await mountHost(120)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(50)

    triggerIntersect(true)
    await flushPromises()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(100)

    triggerIntersect(true)
    await flushPromises()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(120)
    expect(wrapper.vm.sc.isAllLoaded.value).toBe(true)
  })

  it('全部显示后调用 unobserve 停止观察', async () => {
    const wrapper = await mountHost(120)
    expect(ioMock.unobserve).not.toHaveBeenCalled()

    triggerIntersect(true)
    await flushPromises()
    triggerIntersect(true)
    await flushPromises()

    expect(wrapper.vm.sc.displayRecords.value.length).toBe(120)
    expect(ioMock.unobserve).toHaveBeenCalledTimes(1)
  })

  it('420 条：触发至 300 出现"加载剩余"按钮，loadAllRemaining 后全量显示', async () => {
    const wrapper = await mountHost(420)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(50)
    expect(wrapper.vm.sc.showLoadAllButton.value).toBe(false)

    // 50 → 100 → 150 → 200 → 250 → 300
    for (let i = 0; i < 5; i++) {
      triggerIntersect(true)
      await flushPromises()
    }
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(300)
    expect(wrapper.vm.sc.showLoadAllButton.value).toBe(true)

    await wrapper.vm.sc.loadAllRemaining()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(420)
    expect(wrapper.vm.sc.isAllLoaded.value).toBe(true)
  })

  it('数据源重置（records 变化）后首屏回到 50 条', async () => {
    const wrapper = await mountHost(120)
    triggerIntersect(true)
    await flushPromises()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(100)

    // 模拟重新加载：records 替换为 80 条（wrapper.vm 已 proxyRefs 解包，直接赋值写回 ref）
    wrapper.vm.records = makeRecords(80)
    await nextTick()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(50)
  })

  it('组件卸载时 disconnect observer', async () => {
    const wrapper = await mountHost(120)
    wrapper.unmount()
    expect(ioMock.disconnect).toHaveBeenCalledTimes(1)
  })
})

// ══════════════════════════════════════════════════════════════════
// 分页模式（Phase 2）：VITE_USE_PAGINATED_RECORDS_API=true + fetchPage
// ══════════════════════════════════════════════════════════════════

/** 构造分页 fetcher：total 条数据，每页 pageSize 条 */
function makeFetcher(total: number) {
  return vi.fn(async (page: number, pageSize: number) => {
    const start = (page - 1) * pageSize
    const items = Array.from({ length: Math.min(pageSize, total - start) }, (_, i) => ({
      id: start + i + 1,
      name: `n${start + i + 1}`,
    }))
    return {
      items,
      total,
      page,
      pageSize,
      hasMore: start + items.length < total,
    }
  })
}

const PaginatedHost = defineComponent({
  props: { fetcher: { type: Function, required: true } },
  setup(props) {
    const sentinel = ref<HTMLElement | null>(null)
    const sc = useIncrementalScroll(props.fetcher as any, sentinel)
    return { sc, sentinel }
  },
  template: '<div><div ref="sentinel" class="scroll-sentinel" style="height:1px" /></div>',
})

async function mountPaginated(fetcher: (page: number, size: number) => Promise<any>) {
  const wrapper = mount(PaginatedHost, { props: { fetcher } })
  await flushPromises()
  await nextTick()
  return wrapper as any
}

describe('useIncrementalScroll（分页模式，VITE_USE_PAGINATED_RECORDS_API=true）', () => {
  beforeEach(() => {
    import.meta.env.VITE_USE_PAGINATED_RECORDS_API = 'true'
  })
  afterEach(() => {
    import.meta.env.VITE_USE_PAGINATED_RECORDS_API = 'false'
  })

  it('首次加载调用 fetchPage(1, 50)，displayRecords 为第一页', async () => {
    const fetcher = makeFetcher(330)
    const wrapper = await mountPaginated(fetcher)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledWith(1, 50)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(50)
  })

  it('滚动触发 fetchPage(2, 50)，追加到 displayRecords', async () => {
    const fetcher = makeFetcher(330)
    const wrapper = await mountPaginated(fetcher)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(50)

    triggerIntersect(true)
    await flushPromises()
    expect(fetcher).toHaveBeenLastCalledWith(2, 50)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(100)
  })

  it('hasMore=false 后不再触发加载', async () => {
    // 每页 50，第 2 页返回 hasMore=false（100 条总量）
    const fetcher = vi.fn(async (page: number, pageSize: number) => {
      const start = (page - 1) * pageSize
      const items = Array.from({ length: Math.min(pageSize, 100 - start) }, (_, i) => ({ id: start + i + 1 }))
      return { items, total: 100, page, pageSize, hasMore: start + items.length < 100 }
    })
    const wrapper = await mountPaginated(fetcher)
    expect(fetcher).toHaveBeenCalledTimes(1)

    triggerIntersect(true)
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(100)

    // 再次触发：hasMore=false，不再请求
    triggerIntersect(true)
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(100)
    expect(wrapper.vm.sc.isAllLoaded.value).toBe(true)
  })

  it('330 条滚到 300 出现"加载剩余"按钮，loadAllRemaining 拉全量', async () => {
    const fetcher = makeFetcher(330)
    const wrapper = await mountPaginated(fetcher)
    expect(wrapper.vm.sc.showLoadAllButton.value).toBe(false)

    // 50 → 100 → 150 → 200 → 250 → 300
    for (let i = 0; i < 5; i++) {
      triggerIntersect(true)
      await flushPromises()
    }
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(300)
    expect(wrapper.vm.sc.showLoadAllButton.value).toBe(true)

    await wrapper.vm.sc.loadAllRemaining()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(330)
    expect(wrapper.vm.sc.isAllLoaded.value).toBe(true)
  })

  it('降级对照：环境变量为 false 且传 Ref 时走本地切片', async () => {
    import.meta.env.VITE_USE_PAGINATED_RECORDS_API = 'false'
    const wrapper = await mountHost(120)
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(50)
    triggerIntersect(true)
    await flushPromises()
    expect(wrapper.vm.sc.displayRecords.value.length).toBe(100)
  })
})
