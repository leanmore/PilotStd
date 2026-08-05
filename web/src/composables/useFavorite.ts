// web/src/composables/useFavorite.ts
// 收藏状态管理 — 二元状态机（已收藏/未收藏），与归档任务彻底解耦

import { ref, type Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { addFavorite, getBatchFavoriteStatus, removeFavorite } from '@/api/announce'
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

  // ── 批量加载收藏状态（分片 + 并发控制，适配后端 max_length=500）──

  async function loadFavStatuses() {
    if (!records.value.length) return

    const ids = records.value.map(r => r.id)
    const BATCH_SIZE = 500
    const CONCURRENCY = 3

    try {
      let merged: Record<string, any> = {}

      if (ids.length <= BATCH_SIZE) {
        const res = await getBatchFavoriteStatus(ids)
        merged = res.statuses || {}
      } else {
        const chunks: number[][] = []
        for (let i = 0; i < ids.length; i += BATCH_SIZE) {
          chunks.push(ids.slice(i, i + BATCH_SIZE))
        }
        for (let i = 0; i < chunks.length; i += CONCURRENCY) {
          const batch = chunks.slice(i, i + CONCURRENCY)
          const results = await Promise.all(batch.map(c => getBatchFavoriteStatus(c)))
          results.forEach(r => Object.assign(merged, r.statuses || {}))
        }
      }

      for (const r of records.value) {
        const data = merged[String(r.id)]
        if (data) {
          favMap.value[r.id] = (
            data.status === 'done' ||
            data.status === 'pending' ||
            data.status === 'downloading' ||
            data.status === 'archiving'
          )
        } else {
          favMap.value[r.id] = false
        }
      }
    } catch (e) {
      console.warn('[Favorite] 批量获取状态失败，降级为未收藏', e)
      records.value.forEach(r => {
        favMap.value[r.id] = false
      })
    }
  }

  return {
    favMap,
    favLoadingMap,
    isFavLoading,
    toggleFavorite,
    loadFavStatuses,
  }
}
