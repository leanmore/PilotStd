<script setup lang="ts">
defineOptions({ name: 'QuickActionsCard' })
// QuickActionsCard.vue — 快捷操作 Widget（4 个路由跳转按钮）
import { useRouter } from 'vue-router'

const router = useRouter()

const actions = [
  { label: '任务流水线', desc: '扫描→查询→下载→整理→归档', icon: 'pi pi-play', to: '/task', color: '#6366f1' },
  { label: '文件管理', desc: '浏览和管理已下载的文件', icon: 'pi pi-folder', to: '/organize', color: '#f59e0b' },
  { label: '待确认清单', desc: '查看需人工确认的标准', icon: 'pi pi-hourglass', to: '/pending', color: '#3b82f6' },
  { label: '公告检查', desc: '检查标准信息的更新公告', icon: 'pi pi-megaphone', to: '/announce', color: '#10b981' },
]
</script>

<template>
  <div class="actions-widget">
    <div class="widget-header">快捷操作</div>
    <div class="actions-list">
      <button
        v-for="act in actions"
        :key="act.to"
        @click="router.push(act.to)"
        class="action-btn"
      >
        <div class="action-icon" :style="{ background: act.color }">
          <i :class="act.icon" />
        </div>
        <div class="action-text">
          <span class="action-label">{{ act.label }}</span>
          <span class="action-desc">{{ act.desc }}</span>
        </div>
        <i class="pi pi-chevron-right action-arrow" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.actions-widget {
  height: 100%;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.widget-header {
  font-weight: 600;
  color: var(--text-heading);
  font-size: 14px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.actions-list { display: flex; flex-direction: column; gap: 6px; flex: 1; overflow-y: auto; }

.action-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;
  color: var(--text);
  transition: all var(--transition);
  font-size: 13px;
}
.action-btn:hover {
  background: var(--selected);
  border-color: var(--primary-border);
}

.action-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 16px;
}
.action-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.action-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-heading);
}
.action-desc {
  font-size: 11px;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.action-arrow {
  color: var(--text-dim);
  font-size: 12px;
  flex-shrink: 0;
}
</style>
