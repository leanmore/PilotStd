// web/src/composables/useIncrementalScroll.ts
// #40 增量加载：首屏 50 条，滚动触底自动追加，最多 300 条
// 支持"加载全部"按钮一次性跳过上限
import { ref, computed, watch, nextTick, onMounted, onUnmounted, type Ref } from 'vue'

const MAX_DISPLAY = 300
const BATCH_SIZE = 50
const SCROLL_THRESHOLD = 100

export function useIncrementalScroll(allRecords: Ref<any[]>) {
  const displayRecords = ref<any[]>([])
  const isLoadingMore = ref(false)
  // 永久标志位：用户点"加载全部"后增量逻辑永久停止
  const isFullyLoadedByUser = ref(false)

  let _scrollEl: HTMLElement | null = null
  let _lastScrollTs = 0

  function initialize() {
    isFullyLoadedByUser.value = false
    displayRecords.value = allRecords.value.slice(0, BATCH_SIZE)
  }

  // 数据源变更（排序/筛选/重新加载）时自动重置
  watch(allRecords, () => { initialize() }, { immediate: true })

  async function loadMore() {
    if (
      isLoadingMore.value ||
      isFullyLoadedByUser.value ||
      displayRecords.value.length >= Math.min(MAX_DISPLAY, allRecords.value.length)
    ) return

    isLoadingMore.value = true
    await nextTick()

    const currentLen = displayRecords.value.length
    const remaining = allRecords.value.slice(currentLen, currentLen + BATCH_SIZE)
    displayRecords.value = [...displayRecords.value, ...remaining]

    isLoadingMore.value = false
  }

  async function loadAllRemaining() {
    if (isFullyLoadedByUser.value) return

    isLoadingMore.value = true
    await nextTick()

    const remaining = allRecords.value.slice(displayRecords.value.length)
    displayRecords.value = [...displayRecords.value, ...remaining]

    isFullyLoadedByUser.value = true
    isLoadingMore.value = false
  }

  function handleScroll() {
    if (!_scrollEl || isFullyLoadedByUser.value) return
    const now = Date.now()
    if (now - _lastScrollTs < 150) return
    _lastScrollTs = now
    const d = _scrollEl.scrollHeight - _scrollEl.scrollTop - _scrollEl.clientHeight
    if (d < SCROLL_THRESHOLD) loadMore()
  }

  function bindScroll() {
    _scrollEl = document.querySelector('.p-datatable-wrapper') as HTMLElement | null
    if (_scrollEl) {
      _scrollEl.addEventListener('scroll', handleScroll, { passive: true })
    }
  }

  function unbindScroll() {
    if (_scrollEl) {
      _scrollEl.removeEventListener('scroll', handleScroll)
      _scrollEl = null
    }
  }

  onMounted(async () => { await nextTick(); bindScroll() })
  onUnmounted(() => { unbindScroll() })

  const showLoadAllButton = computed(() =>
    !isFullyLoadedByUser.value &&
    displayRecords.value.length >= MAX_DISPLAY &&
    displayRecords.value.length < allRecords.value.length
  )

  const isAllLoaded = computed(() =>
    displayRecords.value.length >= allRecords.value.length
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
