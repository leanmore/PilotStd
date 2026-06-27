// web/src/stores/dashboard.ts — 仪表板布局状态管理（v2：后端存储 + 降级）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/http'
import type { DashboardWidget, LayoutItem } from '@/types/dashboard'
import { createDefaultWidgets } from '@/types/dashboard'

const STORAGE_KEY = 'dashboard_layout'

export const useDashboardStore = defineStore('dashboard', () => {
  const layout = ref<LayoutItem[]>([])
  const widgets = ref<DashboardWidget[]>([])
  const colNum = ref(12)
  const loading = ref(false)
  const loaded = ref(false)

  /** 从后端加载布局 */
  async function loadFromBackend(): Promise<DashboardWidget[] | null> {
    try {
      const r = await http.get('/user/layout')
      if (r.data?.layout) {
        const parsed = JSON.parse(r.data.layout)
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed as DashboardWidget[]
        }
      }
    } catch {
      // 降级到 localStorage
    }
    return null
  }

  /** 同步到后端（静默，不阻塞 UI） */
  async function syncToBackend(data: string) {
    try {
      await http.put('/user/layout', { layout: data })
    } catch {
      // 静默失败，localStorage 兜底
    }
  }

  /** 加载布局：后端 → localStorage → 默认 */
  async function load() {
    if (loaded.value) return
    loading.value = true

    // 1. 优先后端
    const backend = await loadFromBackend()
    if (backend) {
      widgets.value = backend
      layout.value = backend.filter(w => w.visible).map(w => ({ ...w.layout, i: w.id }))
      colNum.value = 12
      loading.value = false
      loaded.value = true
      return
    }

    // 2. 降级 localStorage
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      try {
        const data = JSON.parse(raw)
        if (Array.isArray(data) && data.length > 0) {
          widgets.value = data
          layout.value = data.filter((w: DashboardWidget) => w.visible).map((w: DashboardWidget) => ({ ...w.layout, i: w.id }))
          colNum.value = 12
          // 尝试同步到后端
          syncToBackend(raw)
          loading.value = false
          loaded.value = true
          return
        }
      } catch { /* 损坏，回退默认 */ }
    }

    // 3. 默认布局
    reset()
    loading.value = false
    loaded.value = true
  }

  /** 持久化布局到后端 + localStorage */
  async function save() {
    const data = JSON.stringify(widgets.value)
    localStorage.setItem(STORAGE_KEY, data)
    await syncToBackend(data)
  }

  /** 重置为默认布局并同步 */
  function reset() {
    widgets.value = createDefaultWidgets()
    layout.value = widgets.value.filter(w => w.visible).map(w => ({ ...w.layout, i: w.id }))
    colNum.value = 12
    save()
  }

  /** 添加 Widget */
  function addWidget(widgetType: string) {
    // 检查是否已添加
    if (widgets.value.some(w => w.type === widgetType)) return

    const def = createDefaultWidgets().find(w => w.type === widgetType)
    const existing = widgets.value.filter(w => w.visible)
    const maxY = existing.reduce((m, w) => Math.max(m, w.layout.y + w.layout.h), 0)

    const newWidget: DashboardWidget = def
      ? { ...def, visible: true, layout: { ...def.layout, y: maxY, i: def.layout.i || widgetType } }
      : {
          id: widgetType,
          type: widgetType,
          visible: true,
          layout: { i: widgetType, x: 0, y: maxY, w: 6, h: 3, minW: 2, minH: 2 },
          config: { title: widgetType },
        }

    widgets.value.push(newWidget)
    layout.value.push({ ...newWidget.layout, i: newWidget.id })
    save()
  }

  /** 删除 Widget（标记不可见，保留数据） */
  function removeWidget(widgetId: string) {
    const w = widgets.value.find(w => w.id === widgetId)
    if (w) {
      w.visible = false
      layout.value = layout.value.filter(l => l.i !== widgetId)
      save()
    }
  }

  /** 重新启用 Widget */
  function restoreWidget(widgetId: string) {
    const w = widgets.value.find(w => w.id === widgetId)
    if (w) {
      w.visible = true
      layout.value.push({ ...w.layout, i: w.id })
      save()
    }
  }

  /** 判断 widget 是否可见 */
  function isVisible(widgetType: string): boolean {
    const w = widgets.value.find(w => w.type === widgetType)
    return w ? w.visible : false
  }

  /** 拖拽/缩放完成后同步布局并持久化 */
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

  return {
    layout,
    widgets,
    colNum,
    loading,
    loaded,
    load,
    save,
    reset,
    addWidget,
    removeWidget,
    restoreWidget,
    isVisible,
    onLayoutUpdated,
  }
})
