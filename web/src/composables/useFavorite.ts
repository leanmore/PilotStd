// web/src/composables/useFavorite.ts
// 收藏状态管理 — 仅处理收藏/取消收藏关系，不触发下载或归档轮询

import { ref, type Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { addFavorite, getFavoriteStatus, removeFavorite } from '@/api/announce'
import type { AnnouncementRecord } from '@/types/api'

export function useFavorite(records: Ref<AnnouncementRecord[]>) {
  const toast = useToast()

  const favStatusMap = ref<Record<number, string>>({})
  const favCooldownMap = ref<Record<number, boolean>>({})
  const favLoadingMap = ref<Record<number, boolean>>({})

  function favLabel(status: string) {
    const map: Record<string, string> = {
      pending: '待归档',
      downloading: '下载中',
      archiving: '归档中',
      already_exists: '已收藏',
    }
    const label = map[status]
    if (!label) {
      console.warn('[useFavorite] 未映射的收藏状态:', status)
      return status
    }
    return label
  }

  function favIcon(recordId: number) {
    const s = favStatusMap.value[recordId]
    if (s === 'done') return 'pi pi-star-fill'
    if (s === 'downloading' || s === 'archiving') return 'pi pi-spin pi-spinner'
    if (s === 'failed' || s === 'abandoned') return 'pi pi-exclamation-triangle'
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
        toast.add({ severity: 'success', summary: '已取消收藏', life: 2000 })
      } catch {
        toast.add({ severity: 'error', summary: '取消失败', life: 3000 })
      }
      return
    }
    // already_exists / pending / downloading / archiving 均视为已收藏，不重复提交
    if (current && current !== 'failed' && current !== 'abandoned') return

    favLoadingMap.value[record.id] = true
    try {
      const res = await addFavorite(record.id)
      if (res.status === 'already_exists') {
        // 恢复后端存储的真实状态，避免前端显示 "already_exists"
        favStatusMap.value[record.id] = (res as any).current_status || 'pending'
        toast.add({ severity: 'info', summary: '已收藏', life: 2000 })
      } else {
        favStatusMap.value[record.id] = res.status
        toast.add({ severity: 'success', summary: '已收藏', life: 2000 })
      }
    } catch {
      toast.add({ severity: 'error', summary: '收藏失败', life: 3000 })
    } finally {
      favLoadingMap.value[record.id] = false
    }
  }

  async function loadFavStatuses() {
    const results = await Promise.allSettled(
      records.value.map(r => getFavoriteStatus(r.id).catch(() => ({ status: null })))
    )
    results.forEach((res, i) => {
      if (res.status === 'fulfilled' && res.value.status) {
        favStatusMap.value[records.value[i].id] = res.value.status
        favCooldownMap.value[records.value[i].id] = !!(res.value as any).in_cooldown
      }
    })
  }

  return {
    favStatusMap,
    favCooldownMap,
    favLabel,
    favIcon,
    isFavLoading,
    toggleFavorite,
    loadFavStatuses,
  }
}
