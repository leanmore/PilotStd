<script setup lang="ts">
defineOptions({ name: 'HomeView' })
import { ref, computed, onMounted } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
import { useDashboardStore } from '@/stores/dashboard'
import WidgetManager from '@/components/dashboard/WidgetManager.vue'
import StatsCard from '@/components/dashboard/widgets/StatsCard.vue'
import AdapterStatusAnnounceCard from '@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue'
import AdapterStatusQueryCard from '@/components/dashboard/widgets/AdapterStatusQueryCard.vue'
import RecentAnnounceCard from '@/components/dashboard/widgets/RecentAnnounceCard.vue'
import QuickActionsCard from '@/components/dashboard/widgets/QuickActionsCard.vue'
import PendingItemsCard from '@/components/dashboard/widgets/PendingItemsCard.vue'
import SystemInfoCard from '@/components/dashboard/widgets/SystemInfoCard.vue'
import PlaceholderWidget from '@/components/dashboard/widgets/PlaceholderWidget.vue'
import Button from 'primevue/button'

const store = useDashboardStore()
const showManager = ref(false)

// 异步加载布局
onMounted(async () => {
  await store.load()
})

const visibleWidgets = computed(() => store.widgets.filter(w => w.visible))

const layout = computed({
  get: () => visibleWidgets.value.map(w => ({ ...w.layout, i: w.id })),
  set: (v) => store.onLayoutUpdated(v),
})

function getWidgetComponent(type: string) {
  const map: Record<string, unknown> = {
    'adapter-announce': AdapterStatusAnnounceCard,
    'adapter-query': AdapterStatusQueryCard,
    'stats-summary': StatsCard,
    'recent-tasks': RecentAnnounceCard,
    'quick-actions': QuickActionsCard,
    'pending-items': PendingItemsCard,
    'system-info': SystemInfoCard,
  }
  return map[type] || PlaceholderWidget
}
</script>

<template>
  <div class="dashboard-container" :class="{ 'layout-locked': store.isLocked }">
    <div class="page-header">
      <div>
        <h1>PilotStd</h1>
        <p class="hint">标准管理控制台</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
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

    <GridLayout
      v-if="store.loaded"
      v-model:layout="layout"
      :col-num="store.colNum"
      :row-height="60"
      :is-draggable="!store.isLocked"
      :is-resizable="!store.isLocked"
      :is-mirrored="false"
      :prevent-collision="false"
      :auto-size="true"
      :margin="[16, 16]"
      :use-css-transforms="true"
      :vertical-compact="true"
      :restore-on-drag="false"
      style="min-height: 400px"
    >
      <GridItem
        v-for="widget in visibleWidgets"
        :key="widget.id"
        :i="widget.id"
        :x="widget.layout.x"
        :y="widget.layout.y"
        :w="widget.layout.w"
        :h="widget.layout.h"
        :min-w="widget.layout.minW || 2"
        :min-h="widget.layout.minH || 2"
        class="grid-item-card"
      >
        <component :is="getWidgetComponent(widget.type)" :widget="widget" />
      </GridItem>
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

/* 锁定状态：禁用拖拽/拉伸 */
.layout-locked :deep(.vgl-item__content) {
  cursor: default !important;
}
.layout-locked :deep(.vgl-item__resizer) {
  display: none !important;
}
@media (max-width: 767px) {
  .page-header { margin-bottom: 20px; padding-bottom: 16px; }
  .page-header h1 { font-size: 20px; }
  .hint { font-size: 13px; }
}
</style>
