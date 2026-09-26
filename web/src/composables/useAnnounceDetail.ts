// web/src/composables/useAnnounceDetail.ts
// 公告详情页的取数/解析/编辑/收藏编排 —— 从 views/AnnounceDetail.vue 的 <script setup> 提取
//
// 拆出原因（G-010 文件规模治理）：AnnounceDetail.vue 有效行 487 进入警告区，其中 200+ 行
// 是与模板无关的状态与流程逻辑。提取后组件只剩「组件装配 + 模板」，逻辑可被单独引用与测试。
// 行为不变：所有状态、计算属性、方法名与实现原样搬入，组件按名解构后模板引用不变。

import { ref, onMounted, onBeforeUnmount, computed, type Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import DOMPurify from 'dompurify'
import {
  getAnnounceDetailLite,
  getAnnounceRecords,
  triggerParse,
  getParseStatus,
  updateRecord,
  batchApprove,
} from '@/api/announce'
import type { Announcement, AnnouncementRecord } from '@/types/api'
import type { RecordFetcher } from '@/composables/useIncrementalScroll'
import { useDetailCache } from '@/composables/useDetailCache'
import { useFavorite } from '@/composables/useFavorite'
import { useIncrementalScroll } from '@/composables/useIncrementalScroll'

export function useAnnounceDetail(
  announceNo: string,
  source: string,
  sentinel: Ref<HTMLElement | null>,
) {
  const toast = useToast()

  const { get: getCache, set: setCache, clear: clearDetailCache } = useDetailCache(source, announceNo)

  const loading = ref(true)
  const parsing = ref(false)
  const announcement = ref<Announcement | null>(null)
  const records = ref<AnnouncementRecord[]>([])
  const selectedRecords = ref<AnnouncementRecord[]>([])
  const parseStatus = ref<'pending' | 'parsing' | 'completed' | 'failed'>('pending')

  // ═══ #40 增量加载（方案 C 哨兵 + Phase 2 分页化开关）═══
  const usePaginated = import.meta.env.VITE_USE_PAGINATED_RECORDS_API === 'true'
  // sentinel 由组件声明并以参数传入：模板 ref="sentinel" 是字符串属性，
  // 声明在 composable 内会让 vue-tsc 的 noUnusedLocals 误判为未使用（TS6133）
  const recordsSource: Ref<AnnouncementRecord[]> | RecordFetcher = usePaginated ? (page: number, pageSize: number) => getAnnounceRecords(announceNo, page, pageSize) : records
  const {
    displayRecords,
    isLoadingMore,
    showLoadAllButton,
    loadAllRemaining,
    totalCount,
    reload: reloadRecords,
  } = useIncrementalScroll(recordsSource, sentinel)

  const parseStatusLabel = computed(() => {
    const map: Record<string, string> = {
      pending: '待解析', parsing: '解析中...', completed: '已解析', failed: '解析失败',
    }
    return map[parseStatus.value] || '未知'
  })

  const parseStatusSeverity = computed(() => {
    const map: Record<string, 'secondary' | 'info' | 'success' | 'danger'> = {
      pending: 'secondary', parsing: 'info', completed: 'success', failed: 'danger',
    }
    return map[parseStatus.value] || 'secondary'
  })

  const parseButtonLabel = computed(() => {
    if (parsing.value) return '解析中'
    if (parseStatus.value === 'completed') return '重新解析'
    return '开始解析'
  })

  const parseButtonDisabled = computed(() => {
    if (parsing.value) return true
    if (!announcement.value?.attachment_url) return true
    return false
  })

  const sanitizedContent = computed(() => {
    const raw = DOMPurify.sanitize(announcement.value?.content || '')
    return raw
  })

  async function loadDetail() {
    // 1. 优先读 sessionStorage 缓存
    const cached = getCache()
    if (cached) {
      announcement.value = cached.announcement
      parseStatus.value = cached.parse_status || 'pending'
      // 分页模式：records 走分页接口，缓存不提供记录数据
      if (!usePaginated) records.value = cached.records
      loading.value = false
      loadFavStatuses()
      return
    }

    // 2. 缓存未命中，正常请求
    loading.value = true
    try {
      const res = await getAnnounceDetailLite(announceNo, source, '/announce')
      announcement.value = res.announcement
      parseStatus.value = res.parse_status || 'pending'
      // 分页模式：仅取公告头与解析状态，记录数据由分页接口按页提供
      if (!usePaginated) records.value = res.records || []
      setCache({
        announcement: res.announcement,
        records: usePaginated ? [] : res.records,
        parse_status: res.parse_status,
      })
      loadFavStatuses()
    } catch {
      toast.add({ severity: 'error', summary: '加载失败', detail: '无法加载公告详情', life: 3000 })
    } finally {
      loading.value = false
    }
  }

  async function startParse() {
    if (!announcement.value?.attachment_url) {
      toast.add({ severity: 'warn', summary: '提示', detail: '该公告没有附件', life: 3000 })
      return
    }
    // ✅ #45: 防御性清理已有定时器
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    parsing.value = true
    parseStatus.value = 'parsing'
    try {
      await triggerParse(announceNo)
      let retries = 0
      const maxRetries = 30
      const interval = 2000
      pollTimer = setInterval(async () => {
        retries++
        try {
          const statusRes = await getParseStatus(announceNo)
          if (statusRes.status === 'completed') {
            clearInterval(pollTimer!)
            pollTimer = null
            parseStatus.value = 'completed'
            parsing.value = false
            clearDetailCache()
            await loadDetail()
            // 分页模式：条数取 parse-status 的 record_count；降级模式取本地 records
            const count = usePaginated ? (statusRes.record_count ?? 0) : records.value.length
            toast.add({ severity: 'success', summary: '解析完成', detail: `共 ${count} 条标准`, life: 3000 })
          } else if (statusRes.status === 'failed') {
            clearInterval(pollTimer!)
            pollTimer = null
            parseStatus.value = 'failed'
            parsing.value = false
            toast.add({ severity: 'error', summary: '解析失败', detail: '请检查附件格式', life: 3000 })
          } else if (retries >= maxRetries) {
            clearInterval(pollTimer!)
            pollTimer = null
            parsing.value = false
            toast.add({ severity: 'warn', summary: '超时', detail: '解析超时，请稍后刷新查看', life: 3000 })
          }
        } catch { /* 轮询出错继续 */ }
      }, interval)
    } catch {
      parseStatus.value = 'failed'
      parsing.value = false
      toast.add({ severity: 'error', summary: '启动失败', detail: '无法触发解析任务', life: 3000 })
    }
  }

  function statusLabel(status: string) {
    const map: Record<string, string> = {
      draft: '草稿', pending_review: '待校对', approved: '已确认', rejected: '已驳回',
    }
    return map[status] || status
  }

  function statusSeverity(status: string) {
    const map: Record<string, 'secondary' | 'warn' | 'success' | 'danger'> = {
      draft: 'secondary', pending_review: 'warn', approved: 'success', rejected: 'danger',
    }
    return map[status] || 'secondary'
  }

  async function onCellEditComplete(event: any) {
    const { data, newValue, field } = event
    const oldValue = data[field]
    if (data.status === 'approved') {
      data[field] = oldValue
      toast.add({ severity: 'warn', summary: '提示', detail: '已确认的记录不可编辑', life: 3000 })
      return
    }
    data[field] = newValue
    try {
      await updateRecord(data.id, { [field]: newValue })
      if (data.status === 'draft') {
        data.status = 'pending_review'
      }
      toast.add({ severity: 'success', summary: '保存成功', life: 2000 })
    } catch {
      data[field] = oldValue
      toast.add({ severity: 'error', summary: '保存失败', detail: '请重试', life: 3000 })
    }
  }

  async function handleBatchApprove() {
    const ids = selectedRecords.value.map(r => r.id)
    if (ids.length === 0) return
    try {
      const res = await batchApprove(ids)
      toast.add({ severity: 'success', summary: '确认成功', detail: `已确认 ${res.approved_count} 条标准`, life: 3000 })
      selectedRecords.value = []
      clearDetailCache()
      // 分页模式：重新拉第一页刷新列表；降级模式：重载全量
      if (usePaginated) {
        await reloadRecords()
      } else {
        await loadDetail()
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (Array.isArray(detail?.errors)) {
        toast.add({ severity: 'error', summary: '确认失败', detail: detail.errors.join('；'), life: 5000 })
      } else {
        toast.add({ severity: 'error', summary: '确认失败', detail: '请重试', life: 3000 })
      }
    }
  }

  // ── Phase 4a: 收藏（收藏状态与下载状态分开维护，判定见 @/utils/downloadStatus）──
  // 分页模式下收藏状态基于已加载的 displayRecords（首屏 50 条）

  const { favMap, favStatusMap, isFavLoading, toggleFavorite, loadFavStatuses } = useFavorite(
    usePaginated ? displayRecords : records,
  )

  // ✅ #45: 组件级 pollTimer，确保 onBeforeUnmount 可访问
  let pollTimer: ReturnType<typeof setInterval> | null = null

  onMounted(loadDetail)

  // ✅ #45: 组件卸载时清理轮询定时器
  onBeforeUnmount(() => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  })

  return {
    loading,
    parsing,
    announcement,
    records,
    selectedRecords,
    usePaginated,
    parseStatusLabel,
    parseStatusSeverity,
    parseButtonLabel,
    parseButtonDisabled,
    sanitizedContent,
    startParse,
    statusLabel,
    statusSeverity,
    onCellEditComplete,
    handleBatchApprove,
    displayRecords,
    isLoadingMore,
    showLoadAllButton,
    loadAllRemaining,
    totalCount,
    favMap,
    favStatusMap,
    isFavLoading,
    toggleFavorite,
  }
}
