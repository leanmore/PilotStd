<script setup lang="ts">
import { computed } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
import type { WidgetType } from '@/types/dashboard'
import { useDashboardStore } from '@/stores/dashboard'
import StatsCard from '@/components/dashboard/widgets/StatsCard.vue'
import AdapterStatusCard from '@/components/dashboard/widgets/AdapterStatusCard.vue'
import RecentAnnounceCard from '@/components/dashboard/widgets/RecentAnnounceCard.vue'
import QuickActionsCard from '@/components/dashboard/widgets/QuickActionsCard.vue'

const store = useDashboardStore()

const layout = computed({
  get: () => store.layout,
  set: (v) => store.onLayoutUpdated(v),
})

function getWidgetComponent(type: WidgetType) {
  const map: Record<string, unknown> = {
    'stats-card': StatsCard,
    'adapter-status': AdapterStatusCard,
    'recent-announce': RecentAnnounceCard,
    'quick-actions': QuickActionsCard,
  }
  return map[type]
}
</script>

<template>
  <div class="page-header">
    <div>
      <h1>PilotStd</h1>
      <p class="hint">标准管理控制台</p>
    </div>
  </div>

  <GridLayout
    v-model:layout="layout"
    :col-num="store.colNum"
    :row-height="60"
    :is-draggable="true"
    :is-resizable="true"
    :margin="[16, 16]"
    :use-css-transforms="true"
    :vertical-compact="true"
    style="min-height: 400px"
  >
    <GridItem
      v-for="widget in store.widgets"
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
      <component
        :is="getWidgetComponent(widget.type)"
        :widget="widget"
      />
    </GridItem>
  </GridLayout>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.hint {
  color: var(--text-dim);
  font-size: 13px;
  margin-top: 4px;
}

/* grid-layout-plus 占位符定制 */
:deep(.vgl-item--placeholder) {
  background: var(--primary);
  opacity: 0.12;
  border-radius: var(--radius);
}

/* 网格项过渡 */
:deep(.vgl-item) {
  transition: all 200ms ease;
}

/* 拖拽中的项加阴影 */
:deep(.vgl-item--dragging) {
  box-shadow: var(--shadow-lg);
  z-index: 3;
}
</style>
