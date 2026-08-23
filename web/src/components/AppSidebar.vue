<script setup lang="ts">
/**
 * AppSidebar — 侧边导航栏
 * 包含品牌标识、导航菜单项、底部折叠按钮。
 */
defineOptions({ name: 'AppSidebar' })

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
      <button
        class="collapse-toggle"
        @click="emit('toggle-collapse')"
        :title="sidebarCollapsed ? '展开' : '收起'"
      >
        <i :class="sidebarCollapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'" />
        <span v-show="!sidebarCollapsed">收起</span>
      </button>
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
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.03);
}
.sidebar.collapsed { width: var(--sidebar-width-collapsed); }  /* ✅ #50: 原 72px */

/* 品牌区 */
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: linear-gradient(180deg, var(--surface), var(--surface-raised));
}
.sidebar.collapsed .brand { padding: 20px 0; justify-content: center; }
.brand-icon {
  color: var(--primary);
  font-size: 22px;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(99, 102, 241, 0.3));
}
.brand-text {
  font-size: 17px;
  font-weight: 800;
  color: var(--text-heading);
  letter-spacing: -0.03em;
  white-space: nowrap;
}

/* 导航区 */
nav {
  flex: 1;
  padding: 12px 12px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
nav::-webkit-scrollbar { width: 4px; }
nav::-webkit-scrollbar-track { background: transparent; }
nav::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.sidebar.collapsed nav { padding: 12px 8px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
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
  font-weight: 600;
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
  height: 24px;
  background: linear-gradient(180deg, var(--primary), var(--primary-hover));
  border-radius: 0 4px 4px 0;
  box-shadow: 2px 0 8px rgba(99, 102, 241, 0.3);
}
.sidebar.collapsed .nav-item.active::before { left: 0; }

.nav-item i {
  font-size: 17px;
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
  padding: 12px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--surface-raised);
}
.sidebar.collapsed .sidebar-footer { padding: 12px 8px; }
.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px;
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition);
}
.collapse-toggle:hover {
  background: var(--selected);
  color: var(--text-bright);
  border-color: var(--primary-border);
}
.collapse-toggle i { font-size: 15px; transition: transform var(--transition); }
.collapse-toggle:hover i { transform: scale(1.1); }

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .nav-item { padding: 12px 14px; }
  .collapse-toggle { padding: 12px; }
}
</style>
