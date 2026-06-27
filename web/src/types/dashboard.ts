// web/src/types/dashboard.ts — 仪表板卡片布局类型定义

import type { LayoutItem } from 'grid-layout-plus'

// ── Widget 库定义 ──

export interface WidgetDefinition {
  id: string
  label: string
  description: string
  defaultEnabled: boolean
  defaultLayout: Omit<LayoutItem, 'i'> & { i: string }
  defaultConfig: Record<string, unknown>
}

export const WIDGET_LIBRARY: Record<string, WidgetDefinition> = {
  'adapter-announce': {
    id: 'adapter-announce',
    label: '公告适配器状态',
    description: '展示公告适配器健康度（gb/hb/db）',
    defaultEnabled: true,
    defaultLayout: { i: 'adapter-announce', x: 0, y: 2, w: 6, h: 3, minW: 3, minH: 3 },
    defaultConfig: { title: '公告适配器', refreshInterval: 30 },
  },
  'adapter-query': {
    id: 'adapter-query',
    label: '查询适配器状态',
    description: '展示查询适配器健康度（7个站点）',
    defaultEnabled: true,
    defaultLayout: { i: 'adapter-query', x: 6, y: 2, w: 6, h: 3, minW: 3, minH: 3 },
    defaultConfig: { title: '查询适配器', refreshInterval: 30 },
  },
  'stats-summary': {
    id: 'stats-summary',
    label: '标准库统计',
    description: '现行/废止/待确认/即将实施 概览',
    defaultEnabled: true,
    defaultLayout: { i: 'stats-summary', x: 0, y: 0, w: 12, h: 2, minW: 6, minH: 2 },
    defaultConfig: { title: '标准库统计' },
  },
  'recent-tasks': {
    id: 'recent-tasks',
    label: '最近任务',
    description: '最近执行的后台任务列表',
    defaultEnabled: true,
    defaultLayout: { i: 'recent-tasks', x: 0, y: 5, w: 12, h: 4, minW: 3, minH: 3 },
    defaultConfig: { title: '最近公告', refreshInterval: 0 },
  },
  'pending-items': {
    id: 'pending-items',
    label: '待确认标准',
    description: '待人工确认的标准数量与列表',
    defaultEnabled: false,
    defaultLayout: { i: 'pending-items', x: 0, y: 9, w: 6, h: 3, minW: 3, minH: 3 },
    defaultConfig: { title: '待确认标准' },
  },
  'system-info': {
    id: 'system-info',
    label: '系统信息',
    description: '版本号、运行时间、数据库状态',
    defaultEnabled: false,
    defaultLayout: { i: 'system-info', x: 6, y: 9, w: 6, h: 3, minW: 3, minH: 3 },
    defaultConfig: { title: '系统信息' },
  },
}

// ── 核心类型 ──

export type WidgetType = string

export type { LayoutItem } from 'grid-layout-plus'

export interface DashboardWidget {
  id: string
  type: WidgetType
  layout: LayoutItem
  visible: boolean
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

/** 生成默认布局的纯数据 */
export function createDefaultWidgets(): DashboardWidget[] {
  return Object.values(WIDGET_LIBRARY)
    .filter(w => w.defaultEnabled)
    .map(def => ({
      id: def.id,
      type: def.id,
      visible: true,
      layout: { ...def.defaultLayout },
      config: { ...def.defaultConfig },
    }))
}
