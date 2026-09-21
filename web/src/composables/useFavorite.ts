// web/src/composables/useFavorite.ts
// 收藏状态管理 —— 收藏状态（是否收藏）与下载状态（下到哪一步）解耦维护

import { ref, type Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { addFavorite, getBatchFavoriteStatus, removeFavorite, type BatchFavoriteStatus } from '@/api/announce'
import { isFavorited } from '@/utils/downloadStatus'
import type { AnnouncementRecord } from '@/types/api'

export function useFavorite(records: Ref<AnnouncementRecord[]>) {
  const toast = useToast()

  // 收藏状态：recordId → isFavorited（判定只看后端是否返回收藏对象，见 isFavorited）
  const favMap = ref<Record<number, boolean>>({})
  // 下载状态：recordId → 收藏对象（含 download_status/download_error/last_attempt），供页面渲染进度标签
  const favStatusMap = ref<Record<number, BatchFavoriteStatus>>({})
  // 请求中防抖标记
  const favLoadingMap = ref<Record<number, boolean>>({})

  function isFavLoading(recordId: number) {
    return !!favLoadingMap.value[recordId]
  }

  // ── 乐观更新 + 回滚 ──

  // [FIX-401] 分层错误提示：优先展示后端 detail；断网/超时由全局拦截器统一提示，此处不重复弹窗
  function handleFavoriteError(e: unknown): string | null {
    const err = e as { response?: { status?: number; data?: { detail?: unknown } } }
    if (!err?.response) return null
    const detail = err.response.data?.detail
    if (typeof detail === 'string' && detail) return detail
    return `操作失败 (${err.response.status ?? '未知'})`
  }

  async function toggleFavorite(record: AnnouncementRecord) {
    const id = record.id
    if (favLoadingMap.value[id]) return  // 防重复提交

    const wasFavorited = !!favMap.value[id]
    favLoadingMap.value[id] = true

    if (wasFavorited) {
      // ── 取消收藏（乐观）──
      favMap.value[id] = false
      const prevStatus = favStatusMap.value[id]
      delete favStatusMap.value[id]
      try {
        await removeFavorite(id)
        toast.add({ severity: 'success', summary: '已取消收藏', life: 2000 })
      } catch (e) {
        favMap.value[id] = true  // 回滚
        if (prevStatus) favStatusMap.value[id] = prevStatus
        const msg = handleFavoriteError(e)
        if (msg) toast.add({ severity: 'error', summary: msg, life: 3000 })
      } finally {
        favLoadingMap.value[id] = false
      }
    } else {
      // ── 收藏（乐观）──
      favMap.value[id] = true
      // 新收藏尚未取到队列行：先放占位对象，使状态标签显示"待下载"而不是空白
      favStatusMap.value[id] = {
        favorite_id: 0,
        status: 'pending',
        download_status: null,
        download_error: null,
        last_attempt: null,
        download_updated_at: null,
      }
      try {
        await addFavorite(id)
        toast.add({ severity: 'success', summary: '已收藏', life: 2000 })
      } catch (e) {
        favMap.value[id] = false  // 回滚
        delete favStatusMap.value[id]
        const msg = handleFavoriteError(e)
        if (msg) toast.add({ severity: 'error', summary: msg, life: 3000 })
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
        const data = merged[String(r.id)] as BatchFavoriteStatus | null | undefined
        // 判定只看"后端是否返回收藏对象"：下载 failed/abandoned 依然是有效收藏
        favMap.value[r.id] = isFavorited(data)
        if (isFavorited(data)) {
          favStatusMap.value[r.id] = data as BatchFavoriteStatus
        } else {
          delete favStatusMap.value[r.id]
        }
      }
    } catch (e) {
      console.warn('[Favorite] 批量获取状态失败，降级为未收藏', e)
      records.value.forEach(r => {
        favMap.value[r.id] = false
        delete favStatusMap.value[r.id]
      })
    }
  }

  return {
    favMap,
    favStatusMap,
    favLoadingMap,
    isFavLoading,
    toggleFavorite,
    loadFavStatuses,
  }
}
