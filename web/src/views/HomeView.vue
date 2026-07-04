<script setup lang="ts">
defineOptions({ name: 'HomeView' })
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { GridLayout } from 'grid-layout-plus'
import { useDashboardStore } from '@/stores/dashboard'
import type { DashboardWidget } from '@/types/dashboard'
import WidgetManager from '@/components/dashboard/WidgetManager.vue'
import StatsCard from '@/components/dashboard/widgets/StatsCard.vue'
import AdapterStatusAnnounceCard from '@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue'
import AdapterStatusQueryCard from '@/components/dashboard/widgets/AdapterStatusQueryCard.vue'
import RecentAnnounceCard from '@/components/dashboard/widgets/RecentAnnounceCard.vue'
import QuickActionsCard from '@/components/dashboard/widgets/QuickActionsCard.vue'
import PendingItemsCard from '@/components/dashboard/widgets/PendingItemsCard.vue'
import SystemInfoCard from '@/components/dashboard/widgets/SystemInfoCard.vue'
import TaskTrendCard from '@/components/dashboard/widgets/TaskTrendCard.vue'
import SystemLogCard from '@/components/dashboard/widgets/SystemLogCard.vue'
import PlaceholderWidget from '@/components/dashboard/widgets/PlaceholderWidget.vue'
import Button from 'primevue/button'

const store = useDashboardStore()
const showManager = ref(false)
const isLocked = ref(false)
const windowWidth = ref(window.innerWidth)

// 响应式列数：>=1200px 12列 / >=768px 8列 / 其余 4列
const responsiveColNum = computed(() => {
  if (windowWidth.value >= 1200) return 12
  if (windowWidth.value >= 768) return 8
  return 4
})

function onResize() {
  windowWidth.value = window.innerWidth
}

onMounted(async () => {
  await store.load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

// 根据 layout item 的 i 查找对应 widget 配置（需传给子卡片组件）
function getWidgetById(id: string): DashboardWidget | undefined {
  return store.widgets.find(w => w.id === id)
}

// 移除卡片 → 通知 Store 并持久化
function onRemoveWidget(widgetId: string) {
  store.removeWidget(widgetId)
}

function getWidgetComponent(type: string) {
  const map: Record<string, unknown> = {
    'adapter-announce': AdapterStatusAnnounceCard,
    'adapter-query': AdapterStatusQueryCard,
    'stats-summary': StatsCard,
    'recent-tasks': RecentAnnounceCard,
    'quick-actions': QuickActionsCard,
    'pending-items': PendingItemsCard,
    'system-info': SystemInfoCard,
    'task-trend': TaskTrendCard,
    'system-log': SystemLogCard,
  }
  return map[type] || PlaceholderWidget
}
</script>

<template>
  <div class="dashboard-container">
    <div class="page-header">
      <div>
        <h1>PilotStd</h1>
        <p class="hint">标准管理控制台</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <Button
          :icon="isLocked ? 'pi pi-lock' : 'pi pi-unlock'"
          :label="isLocked ? '解锁布局' : '锁定布局'"
          size="small"
          :severity="isLocked ? 'warn' : 'secondary'"
          outlined
          @click="isLocked = !isLocked"
        />
        <Button
          icon="pi pi-cog"
          label="管理卡片"
          size="small"
          severity="secondary"
          outlined
          @click="showManager = true"
        />
      </div>
    </div>

    <WidgetManager :visible="showManager" @close="showManager = false" />

    <!--
      使用 #item 命名槽模式：GridLayout 内部创建 GridItem，v-bind="item"
      直接从 currentLayout.value 取值。拖拽/缩放时内部数据先更新再 compact，
      GridItem 的 x/y/w/h 始终正确，彻底消除回弹。
     -->
    <GridLayout
      v-if="store.loaded"
      :layout="store.layout"
      @layout-updated="store.onLayoutUpdated"
      :col-num="responsiveColNum"
      :row-height="60"
      :is-draggable="!isLocked"
      :is-resizable="!isLocked"
      :is-mirrored="false"
      :prevent-collision="false"
      :auto-size="true"
      :margin="[16, 16]"
      :use-css-transforms="true"
      :vertical-compact="true"
      :restore-on-drag="false"
      style="min-height: 400px"
    >
      <template #item="{ item }">
        <div class="grid-item-inner">
          <!-- 移除按钮：锁定状态下隐藏，button 标签默认被 dragIgnoreFrom 排除 -->
          <button
            v-if="!isLocked"
            class="widget-remove-btn"
            :title="'移除 ' + (getWidgetById(String(item.i))?.config?.title || String(item.i))"
            @click.stop="onRemoveWidget(String(item.i))"
          >
            <span class="pi pi-times" />
          </button>
          <component
            :is="getWidgetComponent(String(item.i))"
            :widget="getWidgetById(String(item.i))"
          />
        </div>
      </template>
    </GridLayout>
    <div v-else style="text-align:center;padding:48px;color:var(--text-dim)">
      加载布局中...
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 2px solid var(--border);
  position: relative;
}
.page-header::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 120px;
  height: 2px;
  background: linear-gradient(90deg, var(--primary), transparent);
}
.hint { color: var(--text-dim); font-size: 14px; margin-top: 6px; font-weight: 400; }

/* 卡片内容容器 */
.grid-item-inner {
  position: relative;
  width: 100%;
  height: 100%;
}

/* 移除按钮：右上角悬浮，非锁定状态 hover 时显示 */
.widget-remove-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 20;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, background 0.2s;
}
.grid-item-inner:hover .widget-remove-btn {
  opacity: 1;
}
.widget-remove-btn:hover {
  background: rgba(239, 68, 68, 0.85);
}

/* grid-layout-plus 样式 */
:deep(.vgl-item--placeholder) {
  background: linear-gradient(135deg, var(--primary-bg), transparent);
  opacity: 0.6;
  border-radius: var(--radius-lg);
  border: 2px dashed var(--primary-border);
}

:deep(.vgl-item) {
  transition: box-shadow 250ms cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: var(--radius-lg);
}

:deep(.vgl-item--dragging) {
  box-shadow: var(--shadow-lg);
  z-index: 10;
  transform: rotate(2deg) scale(1.02);
  transition: none !important;
}

/* 确保调整大小手柄可见且可交互 */
:deep(.vgl-item__resizer) {
  z-index: 100 !important;
  pointer-events: auto !important;
  opacity: 0.3;
  transition: opacity 0.2s;
}

:deep(.vgl-item:hover .vgl-item__resizer) {
  opacity: 1;
}

/* 拖拽光标提示 */
:deep(.vgl-item__content) {
  cursor: grab;
}
:deep(.vgl-item__content:active) {
  cursor: grabbing;
}

@media (max-width: 767px) {
  .page-header { margin-bottom: 20px; padding-bottom: 16px; }
  .page-header h1 { font-size: 20px; }
  .hint { font-size: 13px; }
}
</style>
