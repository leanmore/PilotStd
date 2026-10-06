// web/src/composables/useNotificationLogs.ts
/**
 * 通知日志页的组合式逻辑（T-41 前端子批：从 `NotificationLogsView.vue` 抽出，守 G-010）。
 *
 * **为什么抽 composable**：SFC 把 script/template/style 混在一起会越过 G-010 的有效行警戒线；
 * 抽出逻辑后 `.vue` 只保留「装配 + 模板 + 样式」，逻辑集中在此处便于单测与复用。
 *
 * **契约（零接口变化）**：本函数**返回原脚本的全部公开名**，调用方按同名解构 ⇒
 * 组件对外的 props/emits/slots 与抽出前**完全一致**；`<template>`/`<style>` 未做任何改动。
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getNotificationLogs,
  deleteNotificationLogs,
  getNotificationChannels,
  getNotificationFailedItems,
  type NotificationLog,
  type ChannelSpec,
  type FailedItem,
} from '@/api/notification'
import { getItem, setItem } from '@/lib/storage'

export function useNotificationLogs() {
  const route = useRoute()
  const { t, te } = useI18n()

  const logs = ref<NotificationLog[]>([])
  const total = ref(0)
  const page = ref(Number(getItem('notiflog_page')) || 1)
  const pageSize = 20
  const loading = ref(false)
  const errMsg = ref('')
  const tableHeight = ref(Number(getItem('notiflog_height')) || 400)

  // 拖拽调整高度
  let startY = 0
  let startHeight = 0

  function onResizeStart(e: MouseEvent) {
    e.preventDefault()
    startY = e.clientY
    startHeight = tableHeight.value
    document.addEventListener('mousemove', onResizeMove)
    document.addEventListener('mouseup', onResizeEnd)
  }

  function onResizeMove(e: MouseEvent) {
    const delta = e.clientY - startY
    tableHeight.value = Math.max(200, Math.min(800, startHeight + delta))
  }

  function onResizeEnd() {
    document.removeEventListener('mousemove', onResizeMove)
    document.removeEventListener('mouseup', onResizeEnd)
    setItem('notiflog_height', String(tableHeight.value))
  }

  // 筛选
  // 说明：本页是**诊断工具**（排查"通知有没有发出去"），不是阅读渠道。
  // 故不提供"已读/未读"筛选与显示——渠道（Telegram 等）不提供已读回传，
  // 「已读」只能表示"用户在 Web 界面点过标记"，与"通知是否送达/是否看过"无关。
  const filterChannel = ref<string | null>(null)
  const filterStatus = ref<string | null>(null)
  const filterStartDate = ref<Date | null>(null)
  const filterEndDate = ref<Date | null>(null)

  function loadNotifFilters() {
    try {
      const raw = getItem('notiflog_filters')
      if (!raw) return
      const f = JSON.parse(raw)
      filterChannel.value = f.ch ?? null
      filterStatus.value = f.st ?? null
      filterStartDate.value = f.sd ? new Date(f.sd) : null
      filterEndDate.value = f.ed ? new Date(f.ed) : null
    } catch {
      /* ignore */
    }
  }

  function saveNotifFilters() {
    setItem(
      'notiflog_filters',
      JSON.stringify({
        ch: filterChannel.value,
        st: filterStatus.value,
        sd: filterStartDate.value?.toISOString() ?? null,
        ed: filterEndDate.value?.toISOString() ?? null,
      }),
    )
  }

  watch([filterChannel, filterStatus, filterStartDate, filterEndDate], saveNotifFilters, { deep: true })
  const highlightId = ref<number | null>(null)

  // 详情弹窗
  const detailVisible = ref(false)
  const detailItem = ref<NotificationLog | null>(null)

  // P3：失败明细（**按需加载**——不随列表拉取；自身分页；服务端已脱敏）
  const failedItems = ref<FailedItem[]>([])
  const failedTotal = ref(0)
  const failedPage = ref(1)
  const failedPageSize = 20
  const failedLoaded = ref(false)
  const failedError = ref(false)

  async function loadFailedItems(page = 1) {
    const item = detailItem.value
    if (!item) return
    failedError.value = false
    try {
      const resp = await getNotificationFailedItems(item.id, page, failedPageSize)
      failedItems.value = resp.items ?? []
      failedTotal.value = resp.total ?? 0
      failedPage.value = resp.page ?? page
      failedLoaded.value = true
    } catch (e) {
      // 吞错可见化：失败必须可见（不静默显示"没有明细"）
      failedError.value = true
      failedLoaded.value = false
      console.warn('[notification] failed-items load failed', e)
    }
  }

  /** 技术枚举 → 用户可读文案；未知取值回退 `unknown` 文案（**不暴露原始码**） */
  function errorTypeLabel(raw: string): string {
    const key = `notification.config.error_type.${raw}`
    return te(key) ? t(key) : t('notification.config.error_type.unknown')
  }

  // 清理日志弹窗
  const cleanupVisible = ref(false)
  const cleanupDays = ref(30)
  const cleanupLoading = ref(false)
  const cleanupResult = ref('')

  async function doCleanup() {
    cleanupLoading.value = true
    cleanupResult.value = ''
    try {
      const r = await deleteNotificationLogs(cleanupDays.value)
      cleanupResult.value = t('notification.logs.cleanup_result', { n: r.deleted })
      cleanupVisible.value = false
      loadLogs()
    } catch (e: any) {
      cleanupResult.value = e.response?.data?.error || t('notification.logs.cleanup_failed')
    } finally {
      cleanupLoading.value = false
    }
  }

  /** 渠道元数据（后端 channel_spec 派生）：筛选下拉与显示名都由它构建，不再硬编码渠道清单 */
  const channelSpecs = ref<ChannelSpec[]>([])

  const channelOptions = computed(() => [
    { label: t('notification.logs.status.all'), value: null },
    ...channelSpecs.value.map((s) => ({
      label: te(s.label_key) ? t(s.label_key) : s.name,
      value: s.name,
    })),
  ])
  const statusOptions = computed(() => [
    { label: t('notification.logs.status.all'), value: null },
    { label: t('notification.logs.status.success'), value: 'success' },
    { label: t('notification.logs.status.failed'), value: 'failed' },
  ])

  /** 渠道显示名：按 spec 的 label_key 解析，未知渠道原样回显（保持既有行为） */
  function channelLabel(v: string): string {
    const spec = channelSpecs.value.find((s) => s.name === v)
    return spec && te(spec.label_key) ? t(spec.label_key) : v
  }

  // 渠道清单来自后端声明——新增渠道时本页自动跟随（此前漏过 dingtalk，见 C1 报告）
  onMounted(async () => {
    try {
      channelSpecs.value = (await getNotificationChannels()).channels
    } catch {
      /* 元数据不可用时下拉只剩"全部"，不阻断日志页 */
    }
  })

  function statusSeverity(s: string): 'success' | 'danger' | 'info' {
    if (s === 'success') return 'success'
    if (s === 'failed') return 'danger'
    return 'info'
  }

  function statusLabel(s: string): string {
    return s === 'success' ? t('notification.logs.status.success') : t('notification.logs.status.failed')
  }

  // 事件类型 → i18n key（notification.event.<type>，与配置页共用同一套文案）；未知类型原样回显
  function eventLabel(v: string): string {
    const key = `notification.event.${v}`
    return te(key) ? t(key) : v
  }

  async function loadLogs() {
    loading.value = true
    errMsg.value = ''
    try {
      const formatDate = (d: Date | null) =>
        d
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : undefined
      const r = await getNotificationLogs(
        {
          page: page.value,
          page_size: pageSize,
          channel: filterChannel.value || undefined,
          status: filterStatus.value || undefined,
          start_date: formatDate(filterStartDate.value),
          end_date: formatDate(filterEndDate.value),
        },
        '/notification-logs',
      )
      logs.value = r.items
      total.value = r.total
    } catch (e: any) {
      errMsg.value = e.response?.data?.error || t('notification.logs.load_failed')
    } finally {
      loading.value = false
    }
  }

  function onSearch() {
    page.value = 1
    loadLogs()
  }

  function onReset() {
    filterChannel.value = null
    filterStatus.value = null
    filterStartDate.value = null
    filterEndDate.value = null
    page.value = 1
    loadLogs()
  }

  function onPageChange(p: number) {
    page.value = p
    setItem('notiflog_page', String(p))
    loadLogs()
  }

  function showDetail(item: NotificationLog) {
    detailItem.value = item
    detailVisible.value = true
  }

  // 临时高亮行样式
  function rowClass(item: NotificationLog) {
    return item.id === highlightId.value ? 'highlight-row' : ''
  }

  // 监听 URL highlight 参数
  watch(
    () => route.query.highlight,
    (val) => {
      if (val) {
        highlightId.value = Number(val)
        setTimeout(() => {
          const el = document.querySelector('.highlight-row') as HTMLElement | null
          el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 300)
      }
    },
  )

  const totalPages = () => Math.max(1, Math.ceil(total.value / pageSize))
  const pages = () => {
    const tp = totalPages()
    const p = page.value
    const range: number[] = []
    let start = Math.max(1, p - 2)
    let end = Math.min(tp, p + 2)
    if (end - start < 4) {
      if (start === 1) end = Math.min(tp, start + 4)
      else start = Math.max(1, end - 4)
    }
    for (let i = start; i <= end; i++) range.push(i)
    return range
  }

  onMounted(() => {
    loadNotifFilters()
    loadLogs()
  })
  // ✅ #45: 防御性清理拖拽监听器
  onBeforeUnmount(() => {
    document.removeEventListener('mousemove', onResizeMove)
    document.removeEventListener('mouseup', onResizeEnd)
  })

  // ── 返回原脚本的全部公开名（调用方按同名解构 ⇒ 模板引用逐一对应，零接口变化）──
  return {
    t,
    te,
    logs,
    total,
    page,
    pageSize,
    loading,
    errMsg,
    tableHeight,
    onResizeStart,
    filterChannel,
    filterStatus,
    filterStartDate,
    filterEndDate,
    highlightId,
    detailVisible,
    detailItem,
    failedItems,
    failedTotal,
    failedPage,
    failedPageSize,
    failedLoaded,
    failedError,
    loadFailedItems,
    errorTypeLabel,
    cleanupVisible,
    cleanupDays,
    cleanupLoading,
    cleanupResult,
    doCleanup,
    channelSpecs,
    channelOptions,
    statusOptions,
    channelLabel,
    statusSeverity,
    statusLabel,
    eventLabel,
    loadLogs,
    onSearch,
    onReset,
    onPageChange,
    showDetail,
    rowClass,
    totalPages,
    pages,
  }
}
