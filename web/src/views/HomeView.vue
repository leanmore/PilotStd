<script setup lang="ts">
defineOptions({ name: 'HomeView' })
import { onMounted, watch } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
import { useDashboard } from '@/composables/useDashboard'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const { layout, fetchLayout, handleLayoutUpdated, removeCard, saveLayoutToServer } = useDashboard()

onMounted(fetchLayout)

// 解锁时强制重建 GridLayout 子组件，规避 grid-layout-plus v1.1.1 动态切换缺陷
watch(
  () => appStore.dashboardLocked,
  (locked, wasLocked) => {
    // 解锁：克隆数组触发 GridItem 重新挂载，确保拖拽监听器正确注册
    if (!locked && wasLocked) {
      layout.value = [...layout.value]
    }
    // 锁定：保存当前布局
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
              <button v-if="!appStore.dashboardLocked" class="remove-btn" @click.stop="removeCard(item.i)">&times;</button>
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

/* 主体 */
.dashboard-body { flex: 1; min-height: 0; display: flex; }
.main-area { flex: 1; min-width: 0; padding: 16px; box-sizing: border-box; overflow: auto; }

/* 卡片 */
.card-wrapper { position: relative; width: 100%; height: 100%; }
.card-inner { width: 100%; height: 100%; }
/* semantic color — consistent across all themes */
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
