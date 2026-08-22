// web/src/composables/useIncrementalScroll.ts
// #40 增量加载：首屏 50 条，滚动触底自动追加，最多 300 条
// 方案 C（IntersectionObserver 哨兵）+ Phase 2 分页化双模式：
//   - 分页模式（VITE_USE_PAGINATED_RECORDS_API=true 且传入 fetchPage 函数）：
//     每次加载向后端请求一页（page/pageSize），displayRecords 追加
//   - 降级模式（默认）：全量数据前端分片（原行为）
// 不再依赖任何滚动容器选择器（PrimeVue 4 已不渲染 .p-datatable-wrapper）。
import { ref, shallowRef, computed, watch, nextTick, onUnmounted, type Ref } from 'vue'

const MAX_DISPLAY = 300
const BATCH_SIZE = 50
// rootMargin 底部外扩 100px：哨兵进入视口前 100px 即提前触发，避免"滚到底才加载"的卡顿
const SENTINEL_ROOT_MARGIN = '0px 0px 100px 0px'

// 分页接口响应结构（显式定义，禁止内联类型）
export interface PaginatedResult {
  items: any[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

// 分页数据获取函数：由调用方注入（禁止在 composable 内硬编码 API URL）
export type RecordFetcher = (page: number, pageSize: number) => Promise<PaginatedResult>

export function useIncrementalScroll(
  allRecordsOrFetcher: Ref<any[]> | RecordFetcher,
  sentinelRef: Ref<HTMLElement | null>, // 哨兵元素独立顶层参数，避免嵌套 options 丢失响应式
  chunkSize: number = BATCH_SIZE,
  loadAllThreshold: number = MAX_DISPLAY,
) {
  // 每次调用时读取环境变量（测试可切换双模式）
  const usePagination = import.meta.env.VITE_USE_PAGINATED_RECORDS_API === 'true'
  const isPaginated = usePagination && typeof allRecordsOrFetcher === 'function'
  const fetcher = isPaginated ? (allRecordsOrFetcher as RecordFetcher) : null
  const localRecords = !isPaginated ? (allRecordsOrFetcher as Ref<any[]>) : null

  // shallowRef：千条级数据只替换整体数组引用，避免深度响应式开销
  const displayRecords = shallowRef<any[]>([])
  const isLoadingMore = ref(false)
  // 永久标志位：用户点"加载全部"后增量逻辑永久停止
  const isFullyLoadedByUser = ref(false)

  let observer: IntersectionObserver | null = null
  // 当前被观察的哨兵元素（unobserve 时需要）
  let _sentinelEl: HTMLElement | null = null

  // ── 分页模式状态 ──
  const serverHasMore = ref(true)
  const totalCount = ref(0)
  const currentPage = ref(0)
  let initialized = false

  // 滚动触发条件：还有可加载数据（受 loadAllThreshold 上限约束，到上限后交"加载剩余"按钮）
  const hasMore = computed(() => {
    if (isPaginated) {
      return serverHasMore.value && displayRecords.value.length < loadAllThreshold
    }
    return displayRecords.value.length < Math.min(loadAllThreshold, localRecords?.value.length ?? 0)
  })

  function initializeLocal() {
    if (!localRecords) return
    isFullyLoadedByUser.value = false
    displayRecords.value = localRecords.value.slice(0, chunkSize)
    totalCount.value = localRecords.value.length
  }

  // 数据源变更（排序/筛选/重新加载）时自动重置（降级模式）
  if (localRecords) {
    watch(localRecords, () => { initializeLocal() }, { immediate: true })
  }

  /** 分页模式：请求一页（replace=true 时替换首屏，否则追加） */
  async function fetchPageOnce(page: number, replace: boolean) {
    if (!fetcher) return
    isLoadingMore.value = true
    try {
      const res = await fetcher(page, chunkSize)
      totalCount.value = res.total
      serverHasMore.value = res.hasMore
      currentPage.value = res.page
      displayRecords.value = replace ? res.items : [...displayRecords.value, ...res.items]
    } finally {
      isLoadingMore.value = false
    }
  }

  /** 分页模式：挂载后加载第一页 */
  async function ensureInitialized() {
    if (!fetcher || initialized) return
    initialized = true
    await fetchPageOnce(1, true)
    maybeUnobserve()
  }

  async function loadMore() {
    if (isLoadingMore.value || isFullyLoadedByUser.value) return

    if (isPaginated) {
      if (!hasMore.value) return
      await fetchPageOnce(currentPage.value + 1, false)
      maybeUnobserve()
      return
    }

    // 降级模式：本地切片追加（原逻辑）
    if (!hasMore.value) return
    isLoadingMore.value = true
    await nextTick()
    const currentLen = displayRecords.value.length
    const remaining = (localRecords?.value ?? []).slice(currentLen, currentLen + chunkSize)
    displayRecords.value = [...displayRecords.value, ...remaining]
    isLoadingMore.value = false
    maybeUnobserve()
  }

  async function loadAllRemaining() {
    if (isFullyLoadedByUser.value) return

    if (isPaginated) {
      // 分页模式：循环拉取剩余页直至 hasMore=false
      try {
        while (serverHasMore.value) {
          await fetchPageOnce(currentPage.value + 1, false)
        }
      } finally {
        isLoadingMore.value = false
      }
      isFullyLoadedByUser.value = true
      maybeUnobserve()
      return
    }

    // 降级模式：一次性追加全部剩余
    isLoadingMore.value = true
    await nextTick()
    const remaining = (localRecords?.value ?? []).slice(displayRecords.value.length)
    displayRecords.value = [...displayRecords.value, ...remaining]
    isFullyLoadedByUser.value = true
    isLoadingMore.value = false
    maybeUnobserve()
  }

  /** 筛选条件变化后重新加载（分页模式重拉第一页，降级模式重置首屏） */
  async function reload() {
    if (isPaginated) {
      isLoadingMore.value = true
      try {
        await fetchPageOnce(1, true)
      } finally {
        isLoadingMore.value = false
      }
      maybeUnobserve()
      return
    }
    initializeLocal()
  }

  /** 全部显示后停止观察哨兵，避免无意义的回调 */
  function maybeUnobserve() {
    const total = isPaginated ? totalCount.value : (localRecords?.value.length ?? 0)
    if (displayRecords.value.length >= total && total > 0 && observer && _sentinelEl) {
      observer.unobserve(_sentinelEl)
    }
  }

  /** 哨兵元素挂载/卸载时创建/销毁 observer（watch 驱动，兼容条件渲染场景） */
  function setupObserver(el: HTMLElement | null) {
    if (observer) {
      observer.disconnect()
      observer = null
      _sentinelEl = null
    }
    if (!el) return

    _sentinelEl = el
    observer = new IntersectionObserver(
      (entries) => {
        // 哨兵进入视口且还有可加载数据时才追加，避免与 isLoading 竞态
        if (entries[0]?.isIntersecting && hasMore.value && !isLoadingMore.value) {
          loadMore()
        }
      },
      { rootMargin: SENTINEL_ROOT_MARGIN },
    )
    observer.observe(el)
  }

  // 哨兵元素通常是条件渲染的（loading 期间不存在），watch 监听其出现后绑定 observer
  watch(sentinelRef, (el) => { setupObserver(el) }, { immediate: true })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
    _sentinelEl = null
  })

  const showLoadAllButton = computed(() => {
    const total = isPaginated ? totalCount.value : (localRecords?.value.length ?? 0)
    return (
      !isFullyLoadedByUser.value &&
      displayRecords.value.length >= loadAllThreshold &&
      displayRecords.value.length < total
    )
  })

  const isAllLoaded = computed(() => {
    const total = isPaginated ? totalCount.value : (localRecords?.value.length ?? 0)
    return total > 0 && displayRecords.value.length >= total
  })

  // 分页模式：挂载后立即加载第一页
  if (isPaginated) {
    ensureInitialized()
  }

  return {
    displayRecords,
    isLoadingMore,
    isAllLoaded,
    showLoadAllButton,
    hasMore,
    totalCount,
    loadMore,
    loadAllRemaining,
    reload,
  }
}
