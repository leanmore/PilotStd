<script setup lang="ts">
// web/src/components/FavoriteStatusTag.vue
// 收藏下载状态标签 —— 收藏页与公告详情页共用（唯一渲染入口）
//
// 边界契约（2026-09-21 定）：
//   status 为 null/undefined（未收藏 / 他人不可见）→ **不渲染任何内容**（星标保持空心由调用方决定）；
//   status 为对象 → 渲染下载状态标签，即使 download_status 为 null（收藏存在但未入队 → "待下载"）。
// G-027：显式声明组件名，防止生产构建压缩掉组件名
defineOptions({ name: 'FavoriteStatusTag' })

import { useI18n } from 'vue-i18n'
import {
  downloadStatusLabel,
  downloadStatusSeverity,
  downloadTooltip,
  truncateError,
} from '@/utils/downloadStatus'

/** 下载队列四字段（列表项与批量状态对象都满足此结构） */
export interface DownloadStatusFields {
  download_status: string | null
  download_error: string | null
  last_attempt: string | null
  download_updated_at?: string | null
}

const props = withDefaults(
  defineProps<{
    status?: DownloadStatusFields | null
    /** 是否在标签下展示失败原因（收藏页列宽足够，公告详情页不展示） */
    showError?: boolean
  }>(),
  { status: null, showError: false },
)

const { t } = useI18n()
</script>

<template>
  <span v-if="props.status" class="fav-status">
    <Tag
      :value="downloadStatusLabel(props.status.download_status, t)"
      :severity="downloadStatusSeverity(props.status.download_status)"
      :title="downloadTooltip(props.status, t)"
    />
    <span
      v-if="props.showError && props.status.download_error"
      class="fav-status-error"
      :title="props.status.download_error"
    >
      {{ truncateError(props.status.download_error) }}
    </span>
  </span>
</template>

<style scoped>
.fav-status {
  display: inline-flex;
  flex-direction: column;
  gap: 0.25rem;
}

.fav-status-error {
  font-size: 0.72rem;
  line-height: 1.25;
  color: var(--text-dim);
  word-break: break-all;
}
</style>
