// web/src/composables/useIncrementalScroll.ts
// #40 增量加载：首屏 50 条，滚动触底自动追加，最多 300 条
import { ref, nextTick, onMounted, onUnmounted, type Ref } from 'vue'

interface UseIncrementalScrollOptions {
  batchSize?: number
  maxDisplay?: number
  minLoadingMs?: number
  scrollThreshold?: number
  throttleMs?: number
}

export function useIncrementalScroll<T>(
  allRecords: Ref<T[]>,
  options: UseIncrementalScrollOptions = {},
) {
  const {
    batchSize = 50,
    maxDisplay = 300,
    minLoadingMs = 300,
    scrollThreshold = 100,
    throttleMs = 150,
  } = options

  const displayRecords = ref<T[]>([]) as Ref<T[]>
  const isLoadingMore = ref(false)
  const isAllLoaded = ref(false)
  let _scrollEl: HTMLElement | null = null

  function throttleFn(fn: (...args: any[]) => void, delay: number) {
    let lastCall = 0
    let timer: ReturnType<typeof setTimeout> | null = null
    return (...args: any[]) => {
      const now = Date.now()
      const remaining = delay - (now - lastCall)
      if (remaining <= 0) {
        if (timer) { clearTimeout(timer); timer = null }
        lastCall = now
        fn(...args)
      } else if (!timer) {
        timer = setTimeout(() => { timer = null; lastCall = Date.now(); fn(...args) }, remaining)
      }
    }
  }

  async function loadNextBatch() {
    if (isLoadingMore.value || isAllLoaded.value) return

    const currentCount = displayRecords.value.length
    const totalCount = allRecords.value.length

    if (currentCount >= totalCount || currentCount >= maxDisplay) {
      isAllLoaded.value = true
      return
    }

    isLoadingMore.value = true
    const start = performance.now()

    await nextTick()

    const nextBatch = allRecords.value.slice(
      currentCount,
      Math.min(currentCount + batchSize, totalCount, maxDisplay),
    )
    displayRecords.value = [...displayRecords.value, ...nextBatch]

    const elapsed = performance.now() - start
    if (elapsed < minLoadingMs) {
      await new Promise(r => setTimeout(r, minLoadingMs - elapsed))
    }

    isLoadingMore.value = false

    if (displayRecords.value.length >= maxDisplay || displayRecords.value.length >= totalCount) {
      isAllLoaded.value = true
    }
  }

  function handleScroll() {
    if (!_scrollEl) return
    const d = _scrollEl.scrollHeight - _scrollEl.scrollTop - _scrollEl.clientHeight
    if (d < scrollThreshold) loadNextBatch()
  }

  const throttledScroll = throttleFn(handleScroll, throttleMs)

  function bindScrollListener() {
    _scrollEl = document.querySelector('.p-datatable-wrapper') as HTMLElement | null
    if (_scrollEl) {
      _scrollEl.addEventListener('scroll', throttledScroll, { passive: true })
    }
  }

  function unbindScrollListener() {
    if (_scrollEl) {
      _scrollEl.removeEventListener('scroll', throttledScroll)
      _scrollEl = null
    }
  }

  function resetDisplay() {
    displayRecords.value = allRecords.value.slice(0, batchSize)
    isAllLoaded.value = allRecords.value.length <= batchSize
    isLoadingMore.value = false
  }

  onMounted(async () => {
    await nextTick()
    bindScrollListener()
  })

  onUnmounted(() => {
    unbindScrollListener()
  })

  return {
    displayRecords,
    isLoadingMore,
    isAllLoaded,
    maxDisplay,
    resetDisplay,
  }
}
