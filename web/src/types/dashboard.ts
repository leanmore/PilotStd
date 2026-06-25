// web/src/types/dashboard.ts — 仪表板卡片布局类型定义

import type { LayoutItem } from 'vue-grid-layout'

// ── 仪表板业务类型 ──

export type WidgetType =
  | 'stats-card'
  | 'adapter-status'
  | 'recent-announce'
  | 'quick-actions'
  | 'task-progress'
  | 'validity-history'

export type { LayoutItem } from 'vue-grid-layout'

export interface DashboardWidget {
  id: string
  type: WidgetType
  layout: LayoutItem
  config: {
    title?: string
    refreshInterval?: number
    [key: string]: unknown
  }
}

export interface DashboardLayoutV1 {
  version: '1.0'
  updatedAt: string
  colNum: number
  widgets: DashboardWidget[]
}
