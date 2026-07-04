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
  try {
    const res = await http.get('/user/layout')
    const raw = res.data?.layout
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) {
        layout.value = hydrateLayout(parsed)
        return
      }
    }
  } catch { /* ignore */ }
  resetLayout()
}

async function saveLayoutToServer(newLayout: any[]) {
  const payload = newLayout.map(({ i, x, y, w, h }) => ({ i, x, y, w, h }))
  try { await http.put('/user/layout', { layout: JSON.stringify(payload) }) } catch { /* ignore */ }
}

function handleLayoutUpdated(newLayout: any[]) {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveLayoutToServer(newLayout), 500)
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

      <aside class="control-sidebar">
        <div class="sidebar-section">
          <label class="sidebar-label">添加卡片</label>
          <div class="sidebar-row">
            <select v-model="selectedCardKey" class="card-select" :disabled="isLocked">
              <option value="" disabled>选择...</option>
              <option v-for="c in availableCards" :key="c.key" :value="c.key">{{ c.label }}</option>
            </select>
            <button class="sidebar-btn add-btn" :disabled="!selectedCardKey || isLocked" @click="addCard">+</button>
          </div>
        </div>

        <div class="sidebar-section">
          <label class="sidebar-label">布局</label>
          <button class="sidebar-btn lock-btn" @click="isLocked = !isLocked">
            {{ isLocked ? '解锁布局' : '锁定布局' }}
          </button>
          <button class="sidebar-btn reset-btn" :disabled="isLocked" @click="resetLayout">重置</button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container { width: 100%; height: 100%; box-sizing: border-box; }
.dashboard-body { display: flex; height: 100%; gap: 0; }
.main-area { flex: 1; min-width: 0; padding: 16px; box-sizing: border-box; overflow: auto; }

/* 右侧控制栏 */
.control-sidebar {
  width: 170px; flex-shrink: 0; padding: 16px 12px; box-sizing: border-box;
  border-left: 1px solid var(--border); background: var(--surface);
  display: flex; flex-direction: column; gap: 20px; overflow-y: auto;
}
.sidebar-section { display: flex; flex-direction: column; gap: 8px; }
.sidebar-label { font-size: 11px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }
.sidebar-row { display: flex; gap: 6px; }
.sidebar-btn {
  width: 100%; height: 32px; padding: 0 10px; border-radius: var(--radius-sm); font-size: 13px;
  cursor: pointer; transition: opacity 0.2s, background 0.2s;
  border: 1px solid var(--border); background: var(--surface); color: var(--text-heading);
  text-align: center; white-space: nowrap;
}
.sidebar-btn:hover { background: var(--primary-bg); }
.sidebar-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.sidebar-btn:disabled:hover { background: var(--surface); }

.lock-btn { font-weight: 600; }
.reset-btn { font-size: 12px; }
.add-btn { background: var(--primary); color: #fff; border-color: var(--primary); font-weight: 700; flex-shrink: 0; width: 32px; }
.add-btn:hover { background: var(--primary-hover, var(--primary)); }

.card-select { flex: 1; padding: 4px 6px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--surface); color: var(--text-heading); font-size: 12px; outline: none; min-width: 0; }

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
