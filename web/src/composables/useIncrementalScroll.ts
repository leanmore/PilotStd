// web/src/composables/useIncrementalScroll.ts
// #40 增量加载：首屏 50 条，滚动触底自动追加，最多 300 条
// 方案 C（修复根因 8ca89221）：IntersectionObserver 监听调用方传入的哨兵元素，
// 不再依赖任何滚动容器选择器（PrimeVue 4 已不渲染 .p-datatable-wrapper，
// 旧 scroll 监听从未绑定，滚动加载从未生效）。
import { ref, computed, watch, nextTick, onUnmounted, type Ref } from 'vue'

const MAX_DISPLAY = 300
const BATCH_SIZE = 50
// rootMargin 底部外扩 100px：哨兵进入视口前 100px 即提前触发，避免"滚到底才加载"的卡顿
const SENTINEL_ROOT_MARGIN = '0px 0px 100px 0px'

export function useIncrementalScroll(
  allRecords: Ref<any[]>,
  sentinelRef: Ref<HTMLElement | null>, // 哨兵元素必须作为独立顶层参数，避免嵌套 options 丢失响应式
) {
  const displayRecords = ref<any[]>([])
  const isLoadingMore = ref(false)
  // 永久标志位：用户点"加载全部"后增量逻辑永久停止
  const isFullyLoadedByUser = ref(false)

  let observer: IntersectionObserver | null = null
  // 当前被观察的哨兵元素（unobserve 时需要）
  let _sentinelEl: HTMLElement | null = null

  // 是否还有可追加的数据（受 300 条上限约束）
  const hasMore = computed(() =>
    displayRecords.value.length < Math.min(MAX_DISPLAY, allRecords.value.length),
  )

  function initialize() {
    isFullyLoadedByUser.value = false
    displayRecords.value = allRecords.value.slice(0, BATCH_SIZE)
  }

  // 数据源变更（排序/筛选/重新加载）时自动重置
  watch(allRecords, () => { initialize() }, { immediate: true })

  async function loadMore() {
    if (isLoadingMore.value || isFullyLoadedByUser.value || !hasMore.value) return

    isLoadingMore.value = true
    await nextTick()

    const currentLen = displayRecords.value.length
    const remaining = allRecords.value.slice(currentLen, currentLen + BATCH_SIZE)
    displayRecords.value = [...displayRecords.value, ...remaining]

    isLoadingMore.value = false
    maybeUnobserve()
  }

  async function loadAllRemaining() {
    if (isFullyLoadedByUser.value) return

    isLoadingMore.value = true
    await nextTick()

    const remaining = allRecords.value.slice(displayRecords.value.length)
    displayRecords.value = [...displayRecords.value, ...remaining]

    isFullyLoadedByUser.value = true
    isLoadingMore.value = false
    maybeUnobserve()
  }

  /** 全部显示后停止观察哨兵，避免无意义的回调 */
  function maybeUnobserve() {
    if (displayRecords.value.length >= allRecords.value.length && observer && _sentinelEl) {
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

  const showLoadAllButton = computed(() =>
    !isFullyLoadedByUser.value &&
    displayRecords.value.length >= MAX_DISPLAY &&
    displayRecords.value.length < allRecords.value.length,
  )

  const isAllLoaded = computed(() =>
    displayRecords.value.length >= allRecords.value.length,
  )

  return {
    displayRecords,
    isLoadingMore,
    isAllLoaded,
    showLoadAllButton,
    loadMore,
    loadAllRemaining,
  }
}
