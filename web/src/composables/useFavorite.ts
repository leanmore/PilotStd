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

  // ── 批量加载收藏状态（单次请求替代 N+1）──

  async function loadFavStatuses() {
    if (!records.value.length) return

    try {
      const res = await getBatchFavoriteStatus(records.value.map(r => r.id))
      const statuses = res.statuses || {}

      for (const r of records.value) {
        const data = statuses[String(r.id)]
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
      // 降级兜底：全部设为未收藏，不阻断页面渲染
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
