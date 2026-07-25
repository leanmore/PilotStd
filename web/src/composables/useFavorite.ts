// web/src/composables/useFavorite.ts
// 收藏状态管理 — 二元状态机（已收藏/未收藏），与归档任务彻底解耦

import { ref, type Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { addFavorite, getFavoriteStatus, removeFavorite } from '@/api/announce'
import type { AnnouncementRecord } from '@/types/api'

export function useFavorite(records: Ref<AnnouncementRecord[]>) {
  const toast = useToast()

  // 二元状态：recordId → isFavorited
  const favMap = ref<Record<number, boolean>>({})
  // 请求中防抖标记
  const favLoadingMap = ref<Record<number, boolean>>({})

  function isFavLoading(recordId: number) {
    return !!favLoadingMap.value[recordId]
  }

  // ── 乐观更新 + 回滚 ──

  async function toggleFavorite(record: AnnouncementRecord) {
    const id = record.id
    if (favLoadingMap.value[id]) return  // 防重复提交

    const wasFavorited = !!favMap.value[id]
    favLoadingMap.value[id] = true

    if (wasFavorited) {
      // ── 取消收藏（乐观）──
      favMap.value[id] = false
      try {
        await removeFavorite(id)
        toast.add({ severity: 'success', summary: '已取消收藏', life: 2000 })
      } catch {
        favMap.value[id] = true  // 回滚
        toast.add({ severity: 'error', summary: '操作失败，请检查网络后重试', life: 3000 })
      } finally {
        favLoadingMap.value[id] = false
      }
    } else {
      // ── 收藏（乐观）──
      favMap.value[id] = true
      try {
        await addFavorite(id)
        toast.add({ severity: 'success', summary: '已收藏', life: 2000 })
      } catch {
        favMap.value[id] = false  // 回滚
        toast.add({ severity: 'error', summary: '操作失败，请检查网络后重试', life: 3000 })
      } finally {
        favLoadingMap.value[id] = false
      }
    }
  }

  // ── 初始化：兼容旧归档状态 → 二元布尔 ──

  async function loadFavStatuses() {
    const results = await Promise.allSettled(
      records.value.map(r => getFavoriteStatus(r.id).catch(() => ({ status: null })))
    )
    results.forEach((res, i) => {
      if (res.status !== 'fulfilled' || !res.value.status) return
      const raw = res.value.status
      // 兼容旧归档状态枚举 → boolean
      favMap.value[records.value[i].id] = (
        raw === 'done' ||
        raw === 'pending' ||
        raw === 'downloading' ||
        raw === 'archiving'
      )
    })
  }

  return {
    favMap,
    favLoadingMap,
    isFavLoading,
    toggleFavorite,
    loadFavStatuses,
  }
}
