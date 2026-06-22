<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useAppStore()

const navItems = [
  { label: t('nav.home'), icon: 'pi pi-home', to: '/' },
  { label: t('nav.task'), icon: 'pi pi-play', to: '/task' },
  { label: t('nav.organize'), icon: 'pi pi-folder', to: '/organize' },
  { label: t('nav.pending'), icon: 'pi pi-hourglass', to: '/pending' },
  { label: t('nav.announce'), icon: 'pi pi-megaphone', to: '/announce' },
  { label: 'API Keys', icon: 'pi pi-key', to: '/admin/api-keys' },
  { label: t('nav.settings'), icon: 'pi pi-cog', to: '/settings' },
]

// 响应式断点
const isDesktop = ref(window.innerWidth >= 1024)
const isTablet = ref(window.innerWidth >= 768 && window.innerWidth < 1024)
const isMobile = ref(window.innerWidth < 768)

// 侧边栏折叠 - 平板默认折叠，桌面默认展开
const sidebarCollapsed = ref(!isDesktop.value)

function onResize() {
  isDesktop.value = window.innerWidth >= 1024
  isTablet.value = window.innerWidth >= 768 && window.innerWidth < 1024
  isMobile.value = window.innerWidth < 768
  // 切换断点时自动调整侧边栏
  if (isMobile.value) {
    sidebarCollapsed.value = true
  } else if (isDesktop.value) {
    sidebarCollapsed.value = false
  } else {
    sidebarCollapsed.value = true
  }
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

// 当前页面标题
const pageTitle = computed(() => {
  const item = navItems.find(n => n.to === route.path)
  return item?.label ?? 'PilotStd'
})

const isDark = computed(() => store.theme === 'dark')

function logout() { router.push('/login') }
</script>

<template>
  <div class="layout" :class="{ mobile: isMobile, collapsed: sidebarCollapsed }">
    <!-- ═══ 顶部导航栏 ═══ -->
    <header class="topbar">
      <div class="topbar-left">
        <button
          v-if="!isMobile"
          class="topbar-btn sidebar-toggle"
          @click="sidebarCollapsed = !sidebarCollapsed"
          :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
        >
          <i class="pi pi-bars" />
        </button>
        <span class="topbar-brand" v-if="isMobile">PilotStd</span>
        <span class="topbar-title">{{ pageTitle }}</span>
      </div>
      <div class="topbar-right">
        <!-- 主题切换 -->
        <button
          class="topbar-btn theme-btn"
          @click="store.toggleTheme()"
          :title="isDark ? '切换亮色主题' : '切换暗色主题'"
        >
          <i :class="isDark ? 'pi pi-sun' : 'pi pi-moon'" />
        </button>
        <!-- 用户信息 -->
        <span class="user-tag" v-if="store.username">
          <i class="pi pi-user" />
          <span class="hide-mobile">{{ store.username }}</span>
        </span>
        <!-- 退出 -->
        <button class="topbar-btn logout-btn" @click="logout" title="退出登录">
          <i class="pi pi-sign-out" />
          <span class="hide-mobile">退出</span>
        </button>
      </div>
    </header>

    <div class="main-area">
      <!-- ═══ 侧边栏 ═══ -->
      <aside v-if="!isMobile" class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="brand">
          <span class="brand-icon">&#9678;</span>
          <span v-show="!sidebarCollapsed" class="brand-text">PilotStd</span>
        </div>
        <nav>
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="{ active: route.path === item.to }"
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
            @click="sidebarCollapsed = !sidebarCollapsed"
            :title="sidebarCollapsed ? '展开' : '收起'"
          >
            <i :class="sidebarCollapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'" />
            <span v-show="!sidebarCollapsed">收起</span>
          </button>
        </div>
      </aside>

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
   顶部导航栏
   ═══════════════════════════════════════════ */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 2px 8px -4px rgba(0, 0, 0, 0.08);
  z-index: 100;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.topbar-brand {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
  letter-spacing: -0.02em;
}

.topbar-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-dim);
  padding-left: 12px;
  border-left: 1px solid var(--border);
}

.topbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
  transition: all var(--transition);
  white-space: nowrap;
}
.topbar-btn:hover {
  background: var(--selected);
  color: var(--text-bright);
}
.topbar-btn i { font-size: 15px; }

.theme-btn:hover { color: var(--warning); }
.logout-btn:hover { color: var(--danger); }

.user-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 13px;
  color: var(--text);
}
.user-tag i { font-size: 14px; color: var(--text-dim); }

/* ═══════════════════════════════════════════
   侧边栏
   ═══════════════════════════════════════════ */
.sidebar {
  width: 240px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
.sidebar.collapsed { width: 64px; }

/* 品牌区 */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 18px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.sidebar.collapsed .brand { padding: 18px 0; justify-content: center; }
.brand-icon {
  color: var(--primary);
  font-size: 20px;
  flex-shrink: 0;
}
.brand-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-heading);
  letter-spacing: -0.02em;
  white-space: nowrap;
}

/* 导航区 */
nav {
  flex: 1;
  padding: 8px 10px;
  overflow-y: auto;
}
.sidebar.collapsed nav { padding: 8px 6px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  color: var(--text-dim);
  text-decoration: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 2px;
  transition: all var(--transition);
  white-space: nowrap;
  overflow: hidden;
  position: relative;
}
.nav-item:hover {
  background: var(--selected);
  color: var(--text);
}
.nav-item.active {
  background: var(--primary-bg);
  color: var(--primary);
}
/* 活跃指示条 */
.nav-item.active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--primary);
  border-radius: 0 3px 3px 0;
}
.sidebar.collapsed .nav-item.active::before { left: -6px; }

.nav-item i {
  font-size: 16px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}
.nav-label { flex: 1; }

/* 侧边栏底部折叠按钮 */
.sidebar-footer {
  padding: 8px 10px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.sidebar.collapsed .sidebar-footer { padding: 8px 6px; }
.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 8px;
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  border-radius: var(--radius-sm);
  font-size: 13px;
  transition: all var(--transition);
}
.collapse-toggle:hover {
  background: var(--selected);
  color: var(--text);
}
.collapse-toggle i { font-size: 14px; }

/* ═══════════════════════════════════════════
   内容区
   ═══════════════════════════════════════════ */
.content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg);
}
.content-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 28px 32px;
}
.layout.mobile .content-inner {
  padding: 16px 14px;
}

/* ═══════════════════════════════════════════
   移动端底部导航（毛玻璃效果 — 参考 MoviePilot）
   ═══════════════════════════════════════════ */
.bottom-nav {
  display: flex;
  justify-content: space-around;
  align-items: center;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  padding: 0 4px;
  padding-bottom: env(safe-area-inset-bottom);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
  z-index: 100;
}
/* 暗色主题下的毛玻璃 */
:root[data-theme="dark"] .bottom-nav {
  background: rgba(22, 29, 44, 0.85);
}

.tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 0;
  min-width: 48px;
  font-size: 10px;
  color: var(--text-dim);
  text-decoration: none;
  border-radius: var(--radius);
  transition: all var(--transition);
}
.tab i { font-size: 17px; transition: transform var(--transition); }
.tab.active {
  color: var(--primary);
}
.tab.active i { transform: scale(1.15); }

/* ═══════════════════════════════════════════
   响应式
   ═══════════════════════════════════════════ */
@media (max-width: 1023px) {
  .content-inner { padding: 20px 18px; }
}
</style>
