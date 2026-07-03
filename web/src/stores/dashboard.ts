// web/src/stores/dashboard.ts — 仪表板布局（v3：统一配置管理）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/http'
import type { DashboardWidget, LayoutItem } from '@/types/dashboard'
import { createDefaultWidgets } from '@/types/dashboard'
import { usePreferencesStore } from './preferences'
import { getItem, setItem } from '@/lib/storage'

const PREF_KEY = 'dashboard_layout'

export const useDashboardStore = defineStore('dashboard', () => {
  const layout = ref<LayoutItem[]>([])
  const widgets = ref<DashboardWidget[]>([])
  const colNum = ref(12)
  const loading = ref(false)
  const loaded = ref(false)
  const isLocked = ref(false)  // 布局锁定状态

  async function load() {
    if (loaded.value) return
    loading.value = true

    // 1. 优先后端 preferences API
    const prefs = usePreferencesStore()
    const backend = await prefs.get<DashboardWidget[]>(PREF_KEY)

    if (backend && Array.isArray(backend) && backend.length > 0) {
      applyWidgets(backend)
      loading.value = false
      loaded.value = true
      return
    }

    // 2. 降级：旧布局 API (/api/user/layout)
    try {
      const r = await http.get('/user/layout')
      if (r.data?.layout) {
        const parsed = JSON.parse(r.data.layout)
        if (Array.isArray(parsed) && parsed.length > 0) {
          applyWidgets(parsed as DashboardWidget[])
          // 迁移到新 preferences API
          prefs.set(PREF_KEY, parsed).catch(() => {})
          loading.value = false
          loaded.value = true
          return
        }
      }
    } catch { /* ignore */ }

    // 3. 降级 localStorage
    const local = getLocalWidgets()
    if (local) {
      applyWidgets(local)
      prefs.set(PREF_KEY, local).catch(() => {})
      loading.value = false
      loaded.value = true
      return
    }

    // 4. 默认布局
    reset()
    loading.value = false
    loaded.value = true

    // 加载锁定状态和卡片可见性（所有路径统一执行）
    const savedLocked = getItem('dashboard_is_locked')
    if (savedLocked !== null) {
      isLocked.value = savedLocked === 'true'
    }
    const savedVisibility = getItem('dashboard_widgets_visibility')
    if (savedVisibility) {
      try {
        const visMap: Record<string, boolean> = JSON.parse(savedVisibility)
        widgets.value.forEach(w => {
          if (visMap[w.id] !== undefined) {
            w.visible = visMap[w.id]
          }
        })
      } catch { /* ignore parse error */ }
    }
  }

  function save() {
    const data = JSON.stringify(widgets.value)
    setItem(PREF_KEY, data)
    // 保存锁定状态
    setItem('dashboard_is_locked', String(isLocked.value))
    // 保存卡片可见性
    const visMap: Record<string, boolean> = {}
    widgets.value.forEach(w => { visMap[w.id] = w.visible })
    setItem('dashboard_widgets_visibility', JSON.stringify(visMap))
    const prefs = usePreferencesStore()
    prefs.set(PREF_KEY, widgets.value).catch((err) => {
      console.warn('保存布局到后端失败，已保留本地缓存:', err)
    })
  }

  function reset() {
    widgets.value = createDefaultWidgets()
    layout.value = widgets.value.filter(w => w.visible).map(w => ({ ...w.layout, i: w.id }))
    colNum.value = 12
    save()
  }

  function applyWidgets(ws: DashboardWidget[]) {
    widgets.value = ws
    layout.value = ws.filter(w => w.visible).map(w => ({ ...w.layout, i: w.id }))
    colNum.value = 12
  }

  function getLocalWidgets(): DashboardWidget[] | null {
    try {
      const raw = getItem(PREF_KEY)
      if (raw) {
        const data = JSON.parse(raw)
        if (Array.isArray(data) && data.length > 0) return data
      }
    } catch { /* ignore */ }
    return null
  }

  function addWidget(widgetType: string) {
    if (widgets.value.some(w => w.type === widgetType)) return
    const def = createDefaultWidgets().find(w => w.type === widgetType)
    const maxY = widgets.value.filter(w => w.visible).reduce((m, w) => Math.max(m, w.layout.y + w.layout.h), 0)
    const newWidget: DashboardWidget = def
      ? { ...def, visible: true, layout: { ...def.layout, y: maxY, i: def.layout.i || widgetType } }
      : {
          id: widgetType, type: widgetType, visible: true,
          layout: { i: widgetType, x: 0, y: maxY, w: 6, h: 3, minW: 2, minH: 2 },
          config: { title: widgetType },
        }
    widgets.value.push(newWidget)
    layout.value.push({ ...newWidget.layout, i: newWidget.id })
    save()
  }

  function removeWidget(widgetId: string) {
    const w = widgets.value.find(w => w.id === widgetId)
    if (w) { w.visible = false; layout.value = layout.value.filter(l => l.i !== widgetId); save() }
  }

  function isVisible(widgetType: string): boolean {
    const w = widgets.value.find(w => w.type === widgetType)
    return w ? w.visible : false
  }

  function onLayoutUpdated(newLayout: LayoutItem[]) {
    layout.value = newLayout
    for (const item of newLayout) {
      const widget = widgets.value.find(w => w.id === item.i)
      if (widget) widget.layout = { ...item }
    }
    save()
  }

  function toggleLayoutLock() {
    isLocked.value = !isLocked.value
    save()
  }

  function toggleWidgetVisibility(widgetId: string) {
    const widget = widgets.value.find(w => w.id === widgetId)
    if (widget) {
      widget.visible = !widget.visible
      layout.value = widgets.value.filter(w => w.visible).map(w => ({ ...w.layout, i: w.id }))
      save()
    }
  }

  return {
    layout, widgets, colNum, loading, loaded, isLocked,
    load, save, reset, addWidget, removeWidget, isVisible, onLayoutUpdated,

    toggleLayoutLock,
    toggleWidgetVisibility,
  }
})
