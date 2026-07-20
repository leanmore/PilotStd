// web/src/composables/useFavorite.ts
// 收藏/归档状态管理 — 从 AnnounceDetail.vue Phase 4a 提取

import { ref, type Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { addFavorite, getFavoriteStatus, removeFavorite } from '@/api/announce'
import type { AnnouncementRecord } from '@/types/api'

export function useFavorite(records: Ref<AnnouncementRecord[]>) {
  const toast = useToast()

  const favStatusMap = ref<Record<number, string>>({})
  const favLoadingMap = ref<Record<number, boolean>>({})
  const favPollTimers = ref<Record<number, ReturnType<typeof setInterval>>>({})

  function favLabel(status: string) {
    const map: Record<string, string> = { pending: '待处理', downloading: '下载中', archiving: '归档中' }
    return map[status] || status
  }

  function favIcon(recordId: number) {
    const s = favStatusMap.value[recordId]
    if (s === 'done') return 'pi pi-star-fill'
    if (s === 'downloading' || s === 'archiving') return 'pi pi-spin pi-spinner'
    if (s === 'failed') return 'pi pi-exclamation-triangle'
    return 'pi pi-star'
  }

  function isFavLoading(recordId: number) {
    return !!favLoadingMap.value[recordId]
  }

  async function toggleFavorite(record: AnnouncementRecord) {
    const current = favStatusMap.value[record.id]
    if (current === 'done') {
      try {
        await removeFavorite(record.id)
        delete favStatusMap.value[record.id]
        stopFavPoll(record.id)
        toast.add({ severity: 'success', summary: '已取消收藏', life: 2000 })
      } catch {
        toast.add({ severity: 'error', summary: '取消失败', life: 3000 })
      }
      return
    }
    if (current && current !== 'failed') return

    favLoadingMap.value[record.id] = true
    try {
      const res = await addFavorite(record.id)
      favStatusMap.value[record.id] = res.status
      if (res.status === 'pending') startFavPoll(record.id)
    } catch {
      toast.add({ severity: 'error', summary: '收藏失败', life: 3000 })
    } finally {
      favLoadingMap.value[record.id] = false
    }
  }

  function startFavPoll(recordId: number) {
    stopFavPoll(recordId)
    let attempts = 0
    favPollTimers.value[recordId] = setInterval(async () => {
      attempts++
      try {
        const res = await getFavoriteStatus(recordId)
        if (res.status === 'done' || res.status === 'failed') {
          stopFavPoll(recordId)
          favStatusMap.value[recordId] = res.status || 'failed'
          toast.add({
            severity: res.status === 'done' ? 'success' : 'error',
            summary: res.status === 'done' ? '归档完成' : '归档失败',
            detail: res.status === 'done' ? '已归档到标准库' : (res.error_message || '请重试'),
            life: 3000,
          })
          return
        }
        if (res.status) favStatusMap.value[recordId] = res.status
      } catch { /* continue */ }
      if (attempts >= 30) {
        stopFavPoll(recordId)
        favStatusMap.value[recordId] = 'failed'
        toast.add({ severity: 'warn', summary: '超时', detail: '归档处理超时', life: 5000 })
      }
    }, 2000)
  }

  function stopFavPoll(recordId: number) {
    if (favPollTimers.value[recordId]) {
      clearInterval(favPollTimers.value[recordId])
      delete favPollTimers.value[recordId]
    }
  }

  async function loadFavStatuses() {
    const results = await Promise.allSettled(
      records.value.map(r => getFavoriteStatus(r.id).catch(() => ({ status: null })))
    )
    results.forEach((res, i) => {
      if (res.status === 'fulfilled' && res.value.status) {
        favStatusMap.value[records.value[i].id] = res.value.status
      }
    })
  }

  function cleanup() {
    Object.keys(favPollTimers.value).forEach(id => stopFavPoll(Number(id)))
  }

  return {
    favStatusMap,
    favLabel,
    favIcon,
    isFavLoading,
    toggleFavorite,
    loadFavStatuses,
    cleanup,
  }
}
