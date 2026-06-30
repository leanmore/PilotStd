<script setup lang="ts">
/**
 * AppLayout — 应用主布局（编排层）
 *
 * 职责：响应式断点检测、侧边栏折叠状态管理、子组件编排。
 * Header / Sidebar 已拆分为独立组件。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

defineOptions({ name: 'AppLayout' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useAppStore()

// ── 导航项配置 ──
const navItems = [
  { label: t('nav.home'), icon: 'pi pi-home', to: '/' },
  { label: t('nav.task'), icon: 'pi pi-play', to: '/task' },
  { label: t('nav.organize'), icon: 'pi pi-folder', to: '/organize' },
  { label: t('nav.pending'), icon: 'pi pi-hourglass', to: '/pending' },
  { label: t('nav.announce'), icon: 'pi pi-megaphone', to: '/announce' },
  { label: t('nav.notification_logs'), icon: 'pi pi-list', to: '/notification-logs' },
  { label: t('nav.standards_status'), icon: 'pi pi-verified', to: '/standards-status' },
  { label: t('nav.settings'), icon: 'pi pi-cog', to: '/settings' },
]

// ── 响应式断点 ──
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

// ── 计算属性 ──
const pageTitle = computed(() => {
  const item = navItems.find(n => n.to === route.path)
  return item?.label ?? 'PilotStd'
})

const isDark = computed(() => store.theme === 'dark')

// ── 事件处理 ──
function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value }
function toggleTheme() { store.theme = isDark.value ? 'light' : 'dark' }
function logout() { router.push('/login') }
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
/* 暗色主题下的毛玻璃 */
:root[data-theme="dark"] .bottom-nav {
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
</style>
