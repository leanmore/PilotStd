// web/src/utils/dashboard-migration.ts — 布局数据版本管理与迁移

import type { DashboardLayoutV1 } from '@/types/dashboard'

const STORAGE_KEY = 'dashboard_layout'
const BACKUP_KEY = 'dashboard_layout_backup'
const CURRENT_VERSION = '1.0'

export function createDefaultLayout(): DashboardLayoutV1 {
  return {
    version: '1.0',
    updatedAt: new Date().toISOString(),
    colNum: 12,
    widgets: [
      {
        id: 'stats-current',
        type: 'stats-card',
        layout: { i: 'stats-current', x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
        config: { title: '现行标准', statKey: 'current' },
      },
      {
        id: 'stats-expired',
        type: 'stats-card',
        layout: { i: 'stats-expired', x: 3, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
        config: { title: '废止标准', statKey: 'expired' },
      },
      {
        id: 'stats-pending',
        type: 'stats-card',
        layout: { i: 'stats-pending', x: 6, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
        config: { title: '待确认', statKey: 'pending' },
      },
      {
        id: 'stats-upcoming',
        type: 'stats-card',
        layout: { i: 'stats-upcoming', x: 9, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
        config: { title: '即将实施', statKey: 'upcoming' },
      },
      {
        id: 'adapters',
        type: 'adapter-status',
        layout: { i: 'adapters', x: 0, y: 2, w: 6, h: 4, minW: 3, minH: 3 },
        config: { title: '适配器状态', refreshInterval: 30 },
      },
      {
        id: 'announcements',
        type: 'recent-announce',
        layout: { i: 'announcements', x: 6, y: 2, w: 6, h: 4, minW: 3, minH: 3 },
        config: { title: '最近公告', refreshInterval: 0 },
      },
    ],
  }
}

export function loadLayout(): DashboardLayoutV1 {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return createDefaultLayout()
  }

  try {
    const data = JSON.parse(raw)
    if (data.version !== CURRENT_VERSION || !Array.isArray(data.widgets) || data.widgets.length === 0) {
      localStorage.setItem(BACKUP_KEY, raw)
      return createDefaultLayout()
    }
    return data as DashboardLayoutV1
  } catch {
    console.warn('[Dashboard] 布局数据损坏，回退默认布局')
    return createDefaultLayout()
  }
}

export function saveLayout(layout: DashboardLayoutV1): void {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      ...layout,
      version: CURRENT_VERSION,
      updatedAt: new Date().toISOString(),
    }),
  )
}

export function resetLayout(): DashboardLayoutV1 {
  const defaults = createDefaultLayout()
  saveLayout(defaults)
  return defaults
}
