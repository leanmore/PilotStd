<script setup lang="ts">
defineOptions({ name: 'HomeView' })
import { onMounted, watch } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
import { useDashboard } from '@/composables/useDashboard'
import { useAppStore } from '@/stores/app'
import AppButton from '@/components/ui/AppButton.vue'

const appStore = useAppStore()
const { layout, fetchLayout, handleLayoutUpdated, removeCard, saveLayoutToServer } = useDashboard()

onMounted(fetchLayout)

// ── grid-layout-plus v1.1.1 已知缺陷 workaround ──
// 动态切换 isDraggable 时库内部微任务调度器（he/Ze）与 Vue 响应式队列不同步，
// 导致 GridItem 的 interact.js 拖拽监听器未重新绑定。解锁时通过 [...layout] 克隆
// 数组强制 GridItem 重新挂载以触发 Ze() 重跑，目录下 k.value.draggable() 正确执行。
// V-10（2026-11-23 认领，原为无主 TODO）：grid-layout-plus workaround。
// 触发条件：grid-layout-plus 升级到 > 1.1.1 后重新评估；若仍复现则保留本段
// 并在 docs/debt/03-open.md V-10 补充「已复现」记录。当前版本 ^1.1.1。
watch(
  () => appStore.dashboardLocked,
  (locked, wasLocked) => {
    if (!locked && wasLocked) {
      layout.value = [...layout.value]
    }
    if (locked && !wasLocked) {
      saveLayoutToServer()
    }
  },
)
</script>

<template>
  <div class="dashboard-container">
    <div class="dashboard-body">
      <div class="main-area">
        <GridLayout
          v-model:layout="layout"
          :col-num="12"
          :row-height="30"
          :is-draggable="!appStore.dashboardLocked"
          :is-resizable="!appStore.dashboardLocked"
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
              <AppButton v-if="!appStore.dashboardLocked" class="remove-btn" @click.stop="removeCard(item.i)"
  size="s"
  type="ghost"
  bare
>&times;</AppButton>
              <component :is="item.component" class="card-inner" :title-key="item.titleKey" />
            </div>
          </GridItem>
        </GridLayout>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container { width: 100%; height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }

/* 主体 */
.dashboard-body { flex: 1; min-height: 0; display: flex; }
.main-area { flex: 1; min-width: 0; padding: var(--space-16); box-sizing: border-box; overflow: auto; }

/* 卡片 */
.card-wrapper { position: relative; width: 100%; height: 100%; }
.card-inner { width: 100%; height: 100%; }
/* semantic color — consistent across all themes */
/* TODO: [Design Debt] #fff 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] rgba(239,68,68,0.85) 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] 22px 无精确令牌，暂不替换，待定令牌后统一处理 */
.remove-btn { position: absolute; top: 6px; right: 6px; z-index: 10; width: 22px; height: 22px; border-radius: 50%; border: none; background: rgba(239,68,68,0.85); color: #fff; font-size: var(--font-size-14); cursor: pointer; opacity: 0; transition: opacity 0.2s; display: flex; align-items: center; justify-content: center; }
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
