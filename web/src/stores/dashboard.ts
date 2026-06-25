// web/src/stores/dashboard.ts — 仪表板布局状态管理

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardWidget, LayoutItem } from '@/types/dashboard'
import {
  loadLayout,
  saveLayout,
  resetLayout as doResetLayout,
} from '@/utils/dashboard-migration'

export const useDashboardStore = defineStore('dashboard', () => {
  const layout = ref<LayoutItem[]>([])
  const widgets = ref<DashboardWidget[]>([])
  const colNum = ref(12)

  /** 从 localStorage 加载布局（首次访问时调用） */
  function load() {
    const data = loadLayout()
    widgets.value = data.widgets
    layout.value = data.widgets.map(w => w.layout)
    colNum.value = data.colNum || 12
  }

  /** 持久化当前布局到 localStorage */
  function save() {
    saveLayout({
      version: '1.0',
      updatedAt: new Date().toISOString(),
      colNum: colNum.value,
      widgets: widgets.value,
    })
  }

  /** 重置为默认布局 */
  function reset() {
    const data = doResetLayout()
    widgets.value = data.widgets
    layout.value = data.widgets.map(w => w.layout)
    colNum.value = data.colNum || 12
  }

  /** 根据 id 查找 widget */
  function getWidget(id: string): DashboardWidget | undefined {
    return widgets.value.find(w => w.id === id)
  }

  /** 拖拽/缩放完成后同步布局数据并持久化 */
  function onLayoutUpdated(newLayout: LayoutItem[]) {
    layout.value = newLayout
    for (const item of newLayout) {
      const widget = widgets.value.find(w => w.id === item.i)
      if (widget) {
        widget.layout = { ...item }
      }
    }
    save()
  }

  // 首次创建 store 时自动加载
  load()

  return {
    layout,
    widgets,
    colNum,
    load,
    save,
    reset,
    getWidget,
    onLayoutUpdated,
  }
})
