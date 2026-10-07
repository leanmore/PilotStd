<script setup lang="ts">
/**
 * AppLayout — 应用主布局（编排层）
 *
 * 职责：只做「装配 + 模板 + 样式」。响应式断点、侧边栏折叠、导航项生成、悬浮工作台与
 * 无障碍键盘处理等逻辑已抽到 `@/composables/useAppLayout`（T-41 前端子批 6(3/3)，见该文件头部
 * 的生命周期/状态作用域说明）；本文件的 `<template>`（含默认插槽 `<slot />` 透传）与 `<style>`
 * 与拆分前**逐字一致** ⇒ 组件对外接口（插槽契约）零变化。
 */
defineOptions({ name: 'AppLayout' })
import { useAppLayout } from '@/composables/useAppLayout'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

const {
  t,
  store,
  route,
  navItems,
  isMobile,
  sidebarCollapsed,
  pageTitle,
  isDark,
  toggleSidebar,
  toggleTheme,
  logout,
  availableCards,
  addCard,
  resetLayout,
  x,
  y,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  menuOpen,
  triggerBtnId,
  dropdownId,
  isHomeRoute,
  isAnnounceDetail,
  closeMenu,
  onFloatingButtonClick,
  onMenuKeydown,
} = useAppLayout()
</script>

<template>
  <div class="layout" :class="{ mobile: isMobile, collapsed: sidebarCollapsed }">
    <!-- ═══ 顶部导航栏 ═══ -->
    <AppHeader
      :is-mobile="isMobile"
      :sidebar-collapsed="sidebarCollapsed"
      :page-title="pageTitle"
      :is-dark="isDark"
      :username="store.username"
      @toggle-sidebar="toggleSidebar"
      @toggle-theme="toggleTheme"
      @logout="logout"
    />

    <div class="main-area">
      <!-- ═══ 侧边栏 ═══ -->
      <AppSidebar
        v-if="!isMobile"
        :sidebar-collapsed="sidebarCollapsed"
        :nav-items="navItems"
        :route-path="route.path"
        @toggle-collapse="toggleSidebar"
      />

      <!-- ═══ 内容区 ═══ -->
      <main class="content">
        <div class="content-inner">
          <slot />
        </div>
      </main>
    </div>

    <!-- ═══ 移动端底部导航（毛玻璃效果） ═══ -->
    <nav v-if="isMobile" class="bottom-nav">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="tab"
        :class="{ active: route.path === item.to }"
      >
        <i :class="item.icon" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- ═══ 全局悬浮按钮（桌面端右下角，路由动态切换，可拖拽） ═══ -->
    <div v-if="!isMobile" class="floating-workspace-menu" :class="{ open: menuOpen }" :style="{ left: x + 'px', top: y + 'px' }">

      <!-- 模式1：公告详情页 — 返回列表 -->
      <button
        v-if="isAnnounceDetail"
        class="floating-workspace-btn"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @click="onFloatingButtonClick"
        :aria-label="t('dashboard.layout.back_to_list')"
      >
        <i class="pi pi-undo" />
      </button>

      <!-- 模式2：首页 — 展开菜单 -->
      <template v-else-if="isHomeRoute">
        <button
          :id="triggerBtnId"
          class="floating-workspace-btn"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @click.stop="onFloatingButtonClick"
          :aria-label="t('dashboard.layout.workspace_menu')"
          aria-haspopup="true"
          :aria-expanded="menuOpen"
          :aria-controls="menuOpen ? dropdownId : undefined"
        >
          <i class="pi pi-th-large" />
        </button>
        <Transition name="menu-fade">
          <div
            v-show="menuOpen"
            :id="dropdownId"
            class="workspace-dropdown"
            role="menu"
            :aria-labelledby="triggerBtnId"
            @click.stop
            @keydown="onMenuKeydown"
          >
            <!-- ① 添加卡片 -->
            <button v-for="card in availableCards" :key="card.key"
                    role="menuitem" class="menu-item" tabindex="0"
                    @click="addCard(card.key); closeMenu()">
              <i class="pi pi-plus" /><span>{{ t('dashboard.layout.add_card', { name: t(card.labelKey) }) }}</span>
            </button>
            <div v-if="availableCards.length === 0"
                 class="menu-item disabled" role="menuitem" aria-disabled="true">
              <span>{{ t('dashboard.layout.all_added') }}</span>
            </div>
            <div class="menu-divider" role="separator" />
            <!-- ② 锁定/解锁布局 -->
            <button role="menuitem" class="menu-item" tabindex="0"
                    @click="store.toggleDashboardLock(); closeMenu()">
              <i :class="store.dashboardLocked ? 'pi pi-lock-open' : 'pi pi-lock'" />
              <span>{{ store.dashboardLocked ? t('dashboard.layout.unlock') : t('dashboard.layout.lock') }}</span>
            </button>
            <div class="menu-divider" role="separator" />
            <!-- ③ 重置布局 -->
            <button role="menuitem" class="menu-item" tabindex="0"
                    @click="resetLayout(); closeMenu()">
              <i class="pi pi-refresh" />
              <span>{{ t('dashboard.layout.reset') }}</span>
            </button>
          </div>
        </Transition>
      </template>

      <!-- 模式3：其他页面 — 返回工作台 -->
      <button
        v-else
        class="floating-workspace-btn"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @click="onFloatingButtonClick"
        :aria-label="t('dashboard.layout.back_to_workspace')"
      >
        <i class="pi pi-home" />
      </button>

    </div>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════
   布局容器
   ═══════════════════════════════════════════ */
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
}
.layout.mobile { padding-bottom: 72px; }

.main-area {
  display: flex;
  flex: 1;
}

/* ═══════════════════════════════════════════
   内容区
   ═══════════════════════════════════════════ */
.content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg);
  scroll-behavior: smooth;
}
.content-inner {
  max-width: 1600px;
  margin: 0 auto;
  padding: 32px 36px;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.layout.mobile .content-inner {
  padding: 20px 16px;
}

/* ═══════════════════════════════════════════
   移动端底部导航（毛玻璃效果）
   ═══════════════════════════════════════════ */
.bottom-nav {
  display: flex;
  justify-content: space-around;
  align-items: center;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 68px;
  padding: 0 8px;
  padding-bottom: env(safe-area-inset-bottom);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border-top: 1px solid rgba(226, 232, 240, 0.5);
  box-shadow: 0 -2px 16px rgba(0, 0, 0, 0.06);
  z-index: 100;
}
/* 暗色主题下的毛玻璃（dark + blue） */
:root[data-theme="dark"] .bottom-nav,
:root[data-theme="blue"] .bottom-nav {
  background: rgba(15, 23, 42, 0.9);
  border-top-color: rgba(51, 65, 85, 0.5);
}

.tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 4px;
  min-width: 56px;
  font-size: 10px;
  font-weight: 500;
  color: var(--text-dim);
  text-decoration: none;
  border-radius: var(--radius);
  transition: all var(--transition);
  position: relative;
}
.tab::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%) scaleX(0);
  width: 24px;
  height: 3px;
  background: var(--primary);
  border-radius: 0 0 3px 3px;
  transition: transform var(--transition);
}
.tab i {
  font-size: 18px;
  transition: all var(--transition);
}
.tab:hover {
  color: var(--text-bright);
  background: var(--selected);
}
.tab:hover i { transform: scale(1.1); }
.tab.active {
  color: var(--primary);
  font-weight: 600;
}
.tab.active::before { transform: translateX(-50%) scaleX(1); }
.tab.active i { transform: scale(1.2); filter: drop-shadow(0 2px 4px rgba(99, 102, 241, 0.3)); }

/* ═══════════════════════════════════════════
   响应式
   ═══════════════════════════════════════════ */

/* 平板端（768px - 1023px） */
@media (max-width: 1023px) {
  .content-inner { padding: 24px 20px; }
}

/* 移动端（< 768px） */
@media (max-width: 767px) {
  .content-inner { padding: 16px 12px; }

  /* 移动端底部导航图标优化 */
  .bottom-nav { height: 64px; }
  .tab { min-width: 48px; padding: 6px 2px; }
  .tab i { font-size: 17px; }
  .tab span { font-size: 9px; }
}

/* 超小屏幕（< 375px） */
@media (max-width: 374px) {
  .tab span { display: none; }
  .tab { min-width: 44px; }
  .tab i { font-size: 20px; }
}

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .tab { padding: 10px 4px; }
}

/* ═══════════════════════════════════════════
   全局悬浮按钮（桌面端右下角，路由动态切换）
   ═══════════════════════════════════════════ */
.floating-workspace-menu {
  position: fixed;
  z-index: 1000;
}

.floating-workspace-btn {
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  background: var(--primary);
  color: #ffffff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(4px);
  cursor: pointer;
  /* 阻止触摸拖拽时触发页面滚动 */
  touch-action: none;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.floating-workspace-btn:hover {
  background: var(--primary-hover);
  transform: scale(1.08);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}
.floating-workspace-btn i { line-height: 1; }

/* 返回图标加粗 — 仅作用于悬浮按钮内的 undo 图标 */
.floating-workspace-btn .pi-undo {
  font-weight: 700;
  -webkit-text-stroke: 0.6px currentColor;
}
.floating-workspace-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* 下拉菜单面板（向上展开） */
.workspace-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  min-width: 200px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 6px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  border: none;
  border-radius: var(--radius);
  background: none;
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
  transition: background 0.15s;
}
.menu-item:hover { background: var(--selected); color: var(--text-bright); }
.menu-item:focus-visible { outline: 2px solid var(--primary); outline-offset: -2px; }
.menu-item i { font-size: 16px; width: 20px; text-align: center; flex-shrink: 0; }
.menu-item.disabled { color: var(--text-dim); cursor: default; pointer-events: none; }
.menu-item.disabled:hover { background: none; color: var(--text-dim); }

.menu-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 6px;
}

/* 菜单过渡动画（向上展开，translateY 取正） */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
