<script setup lang="ts">
defineOptions({ name: 'HomeView' })
import { ref, onMounted, markRaw, type Component } from 'vue'
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

// 卡片注册表
const CARD_REGISTRY: Record<string, { label: string; component: Component; w: number; h: number; minW: number; minH: number }> = {
  stats: { label: '核心统计', component: markRaw(StatsCard), w: 4, h: 6, minW: 3, minH: 4 },
  sysInfo: { label: '系统状态', component: markRaw(SystemInfoCard), w: 4, h: 6, minW: 3, minH: 4 },
  quickActions: { label: '快捷操作', component: markRaw(QuickActionsCard), w: 4, h: 6, minW: 2, minH: 4 },
  announceAdapter: { label: '公告适配器', component: markRaw(AdapterStatusAnnounceCard), w: 6, h: 8, minW: 4, minH: 6 },
  queryAdapter: { label: '查询适配器', component: markRaw(AdapterStatusQueryCard), w: 6, h: 8, minW: 4, minH: 6 },
  recentAnnounce: { label: '最新公告', component: markRaw(RecentAnnounceCard), w: 6, h: 8, minW: 3, minH: 6 },
  pending: { label: '待确认标准', component: markRaw(PendingItemsCard), w: 6, h: 8, minW: 3, minH: 6 },
  trend: { label: '标准库构成', component: markRaw(TaskTrendCard), w: 4, h: 8, minW: 3, minH: 6 },
  sysLog: { label: '系统日志', component: markRaw(SystemLogCard), w: 8, h: 8, minW: 4, minH: 6 },
}

const STORAGE_KEY = 'mp-dashboard-layout'
const layout = ref<any[]>([])
const isLocked = ref(false)
const selectedCardKey = ref('')

const availableCards = ref<{ key: string; label: string }[]>([])

function updateAvailableCards() {
  const currentKeys = new Set(layout.value.map(l => l.i))
  availableCards.value = Object.entries(CARD_REGISTRY)
    .filter(([key]) => !currentKeys.has(key))
    .map(([key, val]) => ({ key, label: val.label }))
}

function saveLayout() {
  const slim = layout.value.map(({ i, x, y, w, h }) => ({ i, x, y, w, h }))
  localStorage.setItem(STORAGE_KEY, JSON.stringify(slim))
  updateAvailableCards()
}

function loadLayout() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      const items = JSON.parse(saved)
      layout.value = items.map((item: any) => ({
        ...item,
        component: CARD_REGISTRY[item.i]?.component,
      }))
    } catch { initDefaultLayout() }
  } else {
    initDefaultLayout()
  }
  updateAvailableCards()
}

function initDefaultLayout() {
  const defaults = ['stats', 'sysInfo', 'quickActions', 'announceAdapter', 'queryAdapter']
  layout.value = defaults.map((key, idx) => {
    const card = CARD_REGISTRY[key]
    return {
      i: key, x: (idx % 3) * 4, y: Math.floor(idx / 3) * 6,
      w: card.w, h: card.h, minW: card.minW, minH: card.minH,
      component: card.component,
    }
  })
}

function addCard() {
  if (!selectedCardKey.value) return
  const card = CARD_REGISTRY[selectedCardKey.value]
  if (!card) return
  layout.value.push({
    i: selectedCardKey.value, x: 0, y: 0,
    w: card.w, h: card.h, minW: card.minW, minH: card.minH,
    component: card.component,
  })
  selectedCardKey.value = ''
}

function removeCard(key: string) {
  layout.value = layout.value.filter(item => item.i !== key)
  saveLayout()
}

onMounted(loadLayout)
</script>

<template>
  <div class="dashboard-container">
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <label class="lock-switch">
        <input type="checkbox" v-model="isLocked" />
        <span class="switch-label">{{ isLocked ? '锁定布局' : '解锁布局' }}</span>
      </label>
      <div class="toolbar-right">
        <select v-model="selectedCardKey" class="card-select">
          <option value="" disabled>添加卡片...</option>
          <option v-for="c in availableCards" :key="c.key" :value="c.key">{{ c.label }}</option>
        </select>
        <button class="add-btn" :disabled="!selectedCardKey" @click="addCard">+</button>
      </div>
    </div>

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
      @update:layout="saveLayout"
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
          <button v-if="!isLocked" class="remove-btn" @click.stop="removeCard(item.i)">×</button>
          <component :is="item.component" class="card-inner" />
        </div>
      </GridItem>
    </GridLayout>
  </div>
</template>

<style scoped>
.dashboard-container {
  width: 100%; height: 100%; padding: 16px; box-sizing: border-box;
  display: flex; flex-direction: column; gap: 12px;
}

/* 工具栏 */
.toolbar {
  display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;
}
.lock-switch { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; color: var(--text-heading); user-select: none; }
.lock-switch input { accent-color: var(--primary); }
.toolbar-right { display: flex; gap: 8px; }
.card-select {
  padding: 5px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--surface); color: var(--text-heading); font-size: 12px; outline: none;
}
.add-btn {
  width: 30px; height: 30px; border-radius: var(--radius-sm); border: 1px solid var(--primary);
  background: var(--primary); color: #fff; font-size: 16px; cursor: pointer; transition: opacity 0.2s;
}
.add-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 卡片包装 */
.card-wrapper { position: relative; width: 100%; height: 100%; }
.card-inner { width: 100%; height: 100%; }
.remove-btn {
  position: absolute; top: 6px; right: 6px; z-index: 10;
  width: 22px; height: 22px; border-radius: 50%; border: none;
  background: rgba(239,68,68,0.85); color: #fff; font-size: 14px;
  cursor: pointer; opacity: 0; transition: opacity 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.card-wrapper:hover .remove-btn { opacity: 1; }

.dashboard-grid { flex: 1; width: 100%; min-height: 400px; }

/* grid-layout-plus 拖拽样式 */
:deep(.vgl-item--placeholder) {
  background: linear-gradient(135deg, var(--primary-bg), transparent);
  opacity: 0.6; border-radius: var(--radius-lg);
  border: 2px dashed var(--primary-border);
}
:deep(.vgl-item) {
  transition: box-shadow 250ms cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: var(--radius-lg);
}
:deep(.vgl-item--dragging) {
  box-shadow: var(--shadow-lg); z-index: 10;
  transform: rotate(2deg) scale(1.02); transition: none !important;
}
:deep(.vgl-item__resizer) {
  z-index: 100 !important; pointer-events: auto !important;
  opacity: 0.3; transition: opacity 0.2s;
}
:deep(.vgl-item:hover .vgl-item__resizer) { opacity: 1; }
:deep(.vgl-item__content) { cursor: grab; }
:deep(.vgl-item__content:active) { cursor: grabbing; }
</style>
