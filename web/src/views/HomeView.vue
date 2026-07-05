<script setup lang="ts">
defineOptions({ name: 'HomeView' })
import { ref, computed, onMounted, markRaw, type Component } from 'vue'
import http from '@/api/http'
import { GridLayout, GridItem } from 'grid-layout-plus'
import StatsCard from '@/components/dashboard/widgets/StatsCard.vue'
import AdapterStatusAnnounceCard from '@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue'
import AdapterStatusQueryCard from '@/components/dashboard/widgets/AdapterStatusQueryCard.vue'
import RecentAnnounceCard from '@/components/dashboard/widgets/RecentAnnounceCard.vue'
import PendingItemsCard from '@/components/dashboard/widgets/PendingItemsCard.vue'
import SystemInfoCard from '@/components/dashboard/widgets/SystemInfoCard.vue'
import QuickActionsCard from '@/components/dashboard/widgets/QuickActionsCard.vue'
import TaskTrendCard from '@/components/dashboard/widgets/TaskTrendCard.vue'
import SystemLogCard from '@/components/dashboard/widgets/SystemLogCard.vue'

const LAYOUT_STORAGE_KEY = 'dashboard_layout'

const CARD_REGISTRY: Record<string, { label: string; zhName?: string; w: number; h: number }> = {
  stats: { label: '核心统计', w: 4, h: 6 },
  sysInfo: { label: '系统状态', w: 4, h: 6 },
  quickActions: { label: '快捷操作', w: 4, h: 6 },
  announceAdapter: { label: '公告适配器', w: 6, h: 8 },
  queryAdapter: { label: '查询适配器', zhName: '查询适配器集群', w: 8, h: 10 },
  recentAnnounce: { label: '最新公告', w: 6, h: 8 },
  pending: { label: '待确认标准', w: 6, h: 8 },
  trend: { label: '标准库构成', w: 4, h: 8 },
  sysLog: { label: '系统日志', w: 8, h: 8 },
}

const COMPONENT_MAP: Record<string, Component> = {
  stats: markRaw(StatsCard),
  sysInfo: markRaw(SystemInfoCard),
  quickActions: markRaw(QuickActionsCard),
  announceAdapter: markRaw(AdapterStatusAnnounceCard),
  queryAdapter: markRaw(AdapterStatusQueryCard),
  recentAnnounce: markRaw(RecentAnnounceCard),
  pending: markRaw(PendingItemsCard),
  trend: markRaw(TaskTrendCard),
  sysLog: markRaw(SystemLogCard),
}

const DEFAULT_LAYOUT = [
  { i: 'stats', x: 0, y: 0, w: 4, h: 6 },
  { i: 'sysInfo', x: 4, y: 0, w: 4, h: 6 },
  { i: 'quickActions', x: 8, y: 0, w: 4, h: 6 },
  { i: 'announceAdapter', x: 0, y: 6, w: 6, h: 8 },
  { i: 'queryAdapter', x: 6, y: 6, w: 8, h: 10 },
]

const layout = ref<any[]>([])
const isLocked = ref(true)
const selectedCardKey = ref('')
const layoutSaved = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | null = null

const availableCards = computed(() => {
  const currentKeys = new Set(layout.value.map(l => l.i))
  return Object.entries(CARD_REGISTRY)
    .filter(([key]) => !currentKeys.has(key))
    .map(([key, val]) => ({ key, label: val.label }))
})

function hydrateLayout(rawLayout: any[]) {
  return rawLayout.map(item => ({
    ...item,
    component: COMPONENT_MAP[item.i],
    zhName: CARD_REGISTRY[item.i]?.zhName,
  })).filter(item => item.component)
}

async function fetchLayout() {
  // 1. 优先读本地缓存（秒开，无网络延迟）
  const cached = localStorage.getItem(LAYOUT_STORAGE_KEY)
  if (cached) {
    try {
      const parsed = JSON.parse(cached)
      if (Array.isArray(parsed) && parsed.length > 0) {
        layout.value = hydrateLayout(parsed)
      }
    } catch { /* ignore */ }
  }

  // 2. 异步拉取服务器配置覆盖本地缓存
  try {
    const res = await http.get('/user/layout')
    const raw = res.data?.layout
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) {
        layout.value = hydrateLayout(parsed)
        localStorage.setItem(LAYOUT_STORAGE_KEY, raw)
        return
      }
    }
  } catch { /* ignore */ }

  // 3. 无缓存且服务器无数据 → 默认布局
  if (!layout.value.length) resetLayout()
}

async function saveLayoutToServer(newLayout?: any[]) {
  const source = newLayout || layout.value
  const payload = source.map(({ i, x, y, w, h }) => ({ i, x, y, w, h }))
  try {
    await http.put('/user/layout', { layout: JSON.stringify(payload) })
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    console.warn('布局保存失败')
  }
}

function handleLayoutUpdated(newLayout: any[]) {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveLayoutToServer(newLayout), 500)
}

async function toggleLayoutLock() {
  isLocked.value = !isLocked.value
  if (isLocked.value) {
    await saveLayoutToServer()
    layoutSaved.value = true
    setTimeout(() => layoutSaved.value = false, 2000)
  }
}

function addCard() {
  if (!selectedCardKey.value) return
  const meta = CARD_REGISTRY[selectedCardKey.value]
  layout.value.push({
    i: selectedCardKey.value, x: 0, y: 0, w: meta.w, h: meta.h,
    component: COMPONENT_MAP[selectedCardKey.value],
    zhName: meta.zhName,
  })
  selectedCardKey.value = ''
}

function removeCard(key: string) {
  layout.value = layout.value.filter(item => item.i !== key)
}

function resetLayout() {
  layout.value = hydrateLayout(JSON.parse(JSON.stringify(DEFAULT_LAYOUT)))
}

onMounted(fetchLayout)

defineExpose({ layout, isLocked, addCard, removeCard, resetLayout })
</script>

<template>
  <div class="dashboard-container">
    <!-- 顶部操作栏 -->
    <header class="dashboard-header">
      <div class="header-left">
        <h2 class="header-title">工作台</h2>
      </div>
      <div class="header-actions">
        <span v-if="layoutSaved" class="saved-hint">布局已保存</span>
        <select v-model="selectedCardKey" class="card-select" :disabled="isLocked">
          <option value="" disabled>添加卡片…</option>
          <option v-for="c in availableCards" :key="c.key" :value="c.key">{{ c.label }}</option>
        </select>
        <button class="header-btn add-btn" :disabled="!selectedCardKey || isLocked" @click="addCard">+</button>
        <button class="header-btn lock-btn" @click="toggleLayoutLock">
          {{ isLocked ? '🔒 锁定布局' : '🔓 解锁布局' }}
        </button>
      </div>
    </header>

    <div class="dashboard-body">
      <div class="main-area">
        <GridLayout
          v-model:layout="layout"
          :col-num="12"
          :row-height="30"
          :is-draggable="!isLocked"
          :is-resizable="!isLocked"
          :vertical-compact="true"
          :use-css-transforms="true"
          :margin="[12, 12]"
          class="dashboard-grid"
          @update:layout="handleLayoutUpdated"
        >
          <GridItem
            v-for="item in layout"
            :key="item.i"
            :i="item.i"
            :x="item.x"
            :y="item.y"
            :w="item.w"
            :h="item.h"
            :min-w="item.minW || 2"
            :min-h="item.minH || 4"
          >
            <div class="card-wrapper">
              <button v-if="!isLocked" class="remove-btn" @click.stop="removeCard(item.i)">&times;</button>
              <component :is="item.component" class="card-inner" :zh-name="item.zhName" />
            </div>
          </GridItem>
        </GridLayout>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container { width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }

/* 顶部操作栏 */
.dashboard-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; flex-shrink: 0;
  border-bottom: 1px solid var(--border); background: var(--surface);
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-title { font-size: 15px; font-weight: 700; color: var(--text-heading); margin: 0; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.saved-hint { font-size: 12px; color: var(--success); white-space: nowrap; }

.header-btn {
  height: 32px; padding: 0 12px; border-radius: var(--radius-sm); font-size: 13px;
  cursor: pointer; transition: opacity 0.2s, background 0.2s;
  border: 1px solid var(--border); background: var(--surface); color: var(--text-heading);
  text-align: center; white-space: nowrap;
}
.header-btn:hover { background: var(--primary-bg); }
.header-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.header-btn:disabled:hover { background: var(--surface); }

.lock-btn { font-weight: 600; }
.add-btn { background: var(--primary); color: #fff; border-color: var(--primary); font-weight: 700; width: 32px; padding: 0; }
.add-btn:hover { background: var(--primary-hover, var(--primary)); }

.card-select {
  padding: 4px 6px; border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--surface); color: var(--text-heading); font-size: 12px; outline: none;
}

/* 主体 */
.dashboard-body { flex: 1; min-height: 0; display: flex; }
.main-area { flex: 1; min-width: 0; padding: 16px; box-sizing: border-box; overflow: auto; }

/* 卡片 */
.card-wrapper { position: relative; width: 100%; height: 100%; }
.card-inner { width: 100%; height: 100%; }
.remove-btn { position: absolute; top: 6px; right: 6px; z-index: 10; width: 22px; height: 22px; border-radius: 50%; border: none; background: rgba(239,68,68,0.85); color: #fff; font-size: 14px; cursor: pointer; opacity: 0; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; }
.card-wrapper:hover .remove-btn { opacity: 1; }
.dashboard-grid { width: 100%; min-height: 400px; }
:deep(.vgl-item--placeholder) { background: linear-gradient(135deg, var(--primary-bg), transparent); opacity: 0.6; border-radius: var(--radius-lg); border: 2px dashed var(--primary-border); }
:deep(.vgl-item) { transition: box-shadow 250ms cubic-bezier(0.4, 0, 0.2, 1); border-radius: var(--radius-lg); }
:deep(.vgl-item--dragging) { box-shadow: var(--shadow-lg); z-index: 10; transform: rotate(2deg) scale(1.02); transition: none !important; }
:deep(.vgl-item__resizer) { z-index: 100 !important; pointer-events: auto !important; opacity: 0.3; transition: opacity 0.2s; }
:deep(.vgl-item:hover .vgl-item__resizer) { opacity: 1; }
:deep(.vgl-item__content) { cursor: grab; }
:deep(.vgl-item__content:active) { cursor: grabbing; }
</style>
