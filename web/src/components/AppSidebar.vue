<script setup lang="ts">
/**
 * AppSidebar — 侧边导航栏
 * 包含品牌标识、导航菜单项、底部折叠按钮。
 */
defineOptions({ name: 'AppSidebar' })

import { useI18n } from 'vue-i18n'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()

interface NavItem {
  label: string
  icon: string
  to: string
}

defineProps<{
  sidebarCollapsed: boolean
  navItems: NavItem[]
  routePath: string
}>()

const emit = defineEmits<{
  (e: 'toggle-collapse'): void
}>()
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
    <!-- 品牌区 -->
    <div class="brand">
      <span class="brand-icon">&#9678;</span>
      <span v-show="!sidebarCollapsed" class="brand-text">PilotStd</span>
    </div>
    <!-- 导航区 -->
    <nav>
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        :class="{ active: routePath === item.to }"
        :title="sidebarCollapsed ? item.label : ''"
      >
        <i :class="item.icon" />
        <span v-show="!sidebarCollapsed" class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
    <!-- 侧边栏底部：折叠按钮 -->
    <div class="sidebar-footer">
      <AppButton
        class="collapse-toggle"
        @click="emit('toggle-collapse')"
        :title="sidebarCollapsed ? t('dashboard.sidebar.expand') : t('dashboard.sidebar.collapse')"
  size="s"
  type="ghost"
  bare
>
        <i :class="sidebarCollapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'" />
        <span v-show="!sidebarCollapsed">{{ t('dashboard.sidebar.collapse') }}</span>
      </AppButton>
    </div>
  </aside>
</template>

<style scoped>
/* ═══════════════════════════════════════════
   侧边栏
   ═══════════════════════════════════════════ */
.sidebar {
  width: var(--sidebar-width-expanded);  /* ✅ #50: 原 250px */
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  /* TODO: [Design Debt] A-52 — 2px 0 8px rgba(0, 0, 0, 0.03) 无精确令牌，暂不替换，待定令牌后统一处理 */
  /* TODO: [Design Debt] 原生阴影与既有 --shadow-* 层级不匹配（半径/扩散/透明度不同），待统一评估（A-52） */
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.03);
}
.sidebar.collapsed { width: var(--sidebar-width-collapsed); }  /* ✅ #50: 原 72px */

/* 品牌区 */
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-20) var(--space-20) var(--space-16);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: linear-gradient(180deg, var(--surface), var(--surface-raised));
}
.sidebar.collapsed .brand { padding: var(--space-20) 0; justify-content: center; }
.brand-icon {
  color: var(--primary);
  font-size: var(--font-size-22);
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(99, 102, 241, 0.3));
}
.brand-text {
  font-size: var(--font-size-17);
  font-weight: var(--font-weight-extrabold);
  color: var(--text-heading);
  letter-spacing: -0.03em;
  white-space: nowrap;
}

/* 导航区 */
nav {
  flex: 1;
  padding: var(--space-12) var(--space-12);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
nav::-webkit-scrollbar { width: 4px; }
nav::-webkit-scrollbar-track { background: transparent; }
nav::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.sidebar.collapsed nav { padding: var(--space-12) var(--space-8); }

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-10) var(--space-14);
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius);
  font-size: var(--font-size-14);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-4);
  transition: all var(--transition);
  white-space: nowrap;
  overflow: hidden;
  position: relative;
}
.nav-item:hover {
  background: var(--selected);
  color: var(--text-bright);
  transform: translateX(2px);
}
.nav-item.active {
  background: linear-gradient(135deg, var(--primary-bg), transparent);
  color: var(--primary);
  font-weight: var(--font-weight-semibold);
  /* TODO: [Design Debt] A-52 — 0 2px 8px rgba(99, 102, 241, 0.08) 无精确令牌，暂不替换，待定令牌后统一处理 */
  /* TODO: [Design Debt] 原生阴影与既有 --shadow-* 层级不匹配（半径/扩散/透明度不同），待统一评估（A-52） */
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.08);
}
/* 活跃指示条 */
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  /* TODO: [Design Debt] A-52 — 24px 无精确令牌，暂不替换，待定令牌后统一处理 */
  height: var(--size-24);
  background: linear-gradient(180deg, var(--primary), var(--primary-hover));
  /* TODO: [Design Debt] A-52 — 0 4px 4px 0 无精确令牌，暂不替换，待定令牌后统一处理 */
  border-radius: 0 4px 4px 0;
  /* TODO: [Design Debt] A-52 — 2px 0 8px rgba(99, 102, 241, 0.3) 无精确令牌，暂不替换，待定令牌后统一处理 */
  /* TODO: [Design Debt] 原生阴影与既有 --shadow-* 层级不匹配（半径/扩散/透明度不同），待统一评估（A-52） */
  box-shadow: 2px 0 8px rgba(99, 102, 241, 0.3);
}
.sidebar.collapsed .nav-item.active::before { left: 0; }

.nav-item i {
  font-size: var(--font-size-17);
  width: 22px;
  text-align: center;
  flex-shrink: 0;
  transition: transform var(--transition);
}
.nav-item:hover i { transform: scale(1.1); }
.nav-item.active i { transform: scale(1.15); }
.nav-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }  /* ✅ #50: 溢出保护 */

/* 侧边栏底部折叠按钮 */
.sidebar-footer {
  padding: var(--space-12);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--surface-raised);
}
.sidebar.collapsed .sidebar-footer { padding: var(--space-12) var(--space-8); }
.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-8);
  width: 100%;
  padding: var(--space-10);
  background: none;
  border: 1px solid var(--border);
  /* fix(a11y): 深色主题 --text-secondary(#94a3b8) on --surface(#334155) 仅 4.04:1（13px 小字不达 AA 4.5）；
     改用 --text-bright（深色 #e2e8f0≈9:1、浅色 #334155≈9:1） */
  color: var(--text-bright);
  cursor: pointer;
  border-radius: var(--radius);
  font-size: var(--font-size-13);
  font-weight: var(--font-weight-medium);
  transition: all var(--transition);
}
.collapse-toggle:hover {
  background: var(--selected);
  color: var(--text-bright);
  border-color: var(--primary-border);
}
.collapse-toggle i { font-size: var(--font-size-15); transition: transform var(--transition); }
.collapse-toggle:hover i { transform: scale(1.1); }

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .nav-item { padding: var(--space-12) var(--space-14); }
  .collapse-toggle { padding: var(--space-12); }
}
</style>
