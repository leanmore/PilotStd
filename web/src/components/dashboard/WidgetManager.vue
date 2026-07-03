<script setup lang="ts">
defineOptions({ name: 'WidgetManager' })
// WidgetManager.vue — 仪表板卡片管理对话框
import { useDashboardStore } from '@/stores/dashboard'
import { WIDGET_LIBRARY } from '@/types/dashboard'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const store = useDashboardStore()

const availableWidgets = Object.values(WIDGET_LIBRARY)
const addedWidgets = () => availableWidgets.filter(w => store.isVisible(w.id))
const notAddedWidgets = () => availableWidgets.filter(w => !store.isVisible(w.id))
</script>

<template>
  <Dialog
    :visible="props.visible"
    @update:visible="emit('close')"
    header="管理卡片"
    :modal="true"
    :style="{ width: '560px' }"
  >
    <div style="display:flex;gap:24px">
      <!-- 可用卡片 -->
      <div style="flex:1">
        <h4 style="margin:0 0 12px;font-size:14px;color:var(--text-heading)">可用卡片</h4>
        <div v-if="notAddedWidgets().length === 0" style="color:var(--text-dim);font-size:13px;padding:16px 0">
          所有卡片已添加
        </div>
        <div
          v-for="w in notAddedWidgets()"
          :key="w.id"
          style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;margin-bottom:6px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface)"
        >
          <div>
            <div style="font-weight:600;font-size:13px">{{ w.label }}</div>
            <div style="font-size:11px;color:var(--text-dim);margin-top:2px">{{ w.description }}</div>
          </div>
          <Button icon="pi pi-plus" size="small" severity="primary" text rounded @click="store.addWidget(w.id)" />
        </div>
      </div>

      <!-- 分隔 -->
      <div style="width:1px;background:var(--border);align-self:stretch" />

      <!-- 已添加卡片 -->
      <div style="flex:1">
        <h4 style="margin:0 0 12px;font-size:14px;color:var(--text-heading)">
          已添加卡片
          <Tag :value="addedWidgets().length" severity="info" style="margin-left:8px" />
        </h4>
        <div v-if="addedWidgets().length === 0" style="color:var(--text-dim);font-size:13px;padding:16px 0">
          暂未添加任何卡片
        </div>
        <div
          v-for="w in addedWidgets()"
          :key="w.id"
          style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;margin-bottom:6px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-raised)"
        >
          <div>
            <div style="font-weight:600;font-size:13px">{{ w.label }}</div>
            <div style="font-size:11px;color:var(--text-dim);margin-top:2px">{{ w.description }}</div>
          </div>
          <Button
            icon="pi pi-times"
            size="small"
            severity="danger"
            text
            rounded
            :disabled="w.defaultEnabled && store.isVisible(w.id)"
            @click="store.removeWidget(w.id)"
          />
        </div>
      </div>
    </div>

    <!-- 布局锁定 + 可见性管理 -->
    <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border)">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <div>
          <div style="font-weight:600;font-size:13px">锁定布局</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:2px">锁定后卡片无法拖拽或拉伸，防止误触</div>
        </div>
        <button
          class="lock-toggle"
          :class="{ active: store.isLocked }"
          @click="store.toggleLayoutLock()"
        >
          <span class="lock-knob" />
        </button>
      </div>
    </div>
  </Dialog>
</template>

<style scoped>
.lock-toggle {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  border: none;
  background: var(--border);
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}
.lock-toggle.active {
  background: var(--primary);
}
.lock-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: white;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.lock-toggle.active .lock-knob {
  transform: translateX(20px);
}
