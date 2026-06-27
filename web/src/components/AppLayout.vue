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
  { label: t('nav.notification_logs'), icon: 'pi pi-list', to: '/notification-logs' },
  { label: t('nav.standards_status'), icon: 'pi pi-verified', to: '/standards-status' },
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

async function handleRestart() {
  if (!confirm('确定要重启并更新 PilotStd 吗？\n\n服务将暂时不可用约 30 秒。')) return
  try {
    const resp = await fetch('/api/system/restart', { method: 'POST' })
    if (resp.ok) {
      // 轮询等待服务恢复
      let retries = 0
      const check = setInterval(async () => {
        retries++
        try {
          const r = await fetch('/api/health')
          if (r.ok) { clearInterval(check); window.location.reload() }
        } catch {}
        if (retries > 30) { clearInterval(check); window.location.reload() }
      }, 2000)
    }
  } catch {
    // 请求已发出但可能没收到响应（容器正在退出），正常轮询
    setTimeout(() => window.location.reload(), 3000)
  }
}

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
          @click="store.theme = isDark ? 'light' : 'dark'"
          :title="isDark ? '切换亮色主题' : '切换暗色主题'"
        >
          <i :class="isDark ? 'pi pi-sun' : 'pi pi-moon'" />
        </button>
        <!-- 用户信息 -->
        <span class="user-tag" v-if="store.username">
          <i class="pi pi-user" />
          <span class="hide-mobile">{{ store.username }}</span>
        </span>
        <!-- 重启并更新 -->
        <button
          class="topbar-btn restart-btn"
          @click="handleRestart"
          title="重启并更新到最新版本"
        >
          <i class="pi pi-refresh" />
          <span class="hide-mobile">重启更新</span>
        </button>
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
  height: 60px;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 4px 12px -4px rgba(0, 0, 0, 0.08);
  z-index: 100;
  flex-shrink: 0;
  position: sticky;
  top: 0;
}

/* 暗色主题下的顶部导航栏 */
:root[data-theme="dark"] .topbar {
  background: rgba(30, 41, 59, 0.85);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar-brand {
  font-size: 18px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.03em;
}

.topbar-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-dim);
  padding-left: 16px;
  border-left: 2px solid var(--border);
}

.topbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius);
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition);
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}
.topbar-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--selected);
  opacity: 0;
  transition: opacity var(--transition);
}
.topbar-btn:hover::before {
  opacity: 1;
}
.topbar-btn:hover {
  color: var(--text-bright);
  border-color: var(--border);
}
.topbar-btn:active {
  transform: scale(0.96);
}
.topbar-btn i {
  font-size: 16px;
  position: relative;
  z-index: 1;
}
.topbar-btn span {
  position: relative;
  z-index: 1;
}

.theme-btn:hover { color: var(--warning); }
.logout-btn:hover { color: var(--danger); }
.restart-btn:hover { color: var(--primary); }

.user-tag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.user-tag i { font-size: 14px; color: var(--primary); }

/* ═══════════════════════════════════════════
   侧边栏
   ═══════════════════════════════════════════ */
.sidebar {
  width: 250px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.03);
}
.sidebar.collapsed { width: 72px; }

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
  color: var(--text-dim);
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
.nav-label { flex: 1; }

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
  color: var(--text-dim);
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
  .topbar { padding: 0 16px; }
  .hide-mobile { display: none; }
}

/* 移动端（< 768px） */
@media (max-width: 767px) {
  .topbar {
    height: 56px;
    padding: 0 12px;
  }
  .topbar-brand { font-size: 16px; }
  .topbar-title { font-size: 13px; padding-left: 12px; }
  .topbar-btn { padding: 6px 10px; }
  .topbar-btn i { font-size: 15px; }

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
  .nav-item { padding: 12px 14px; }
  .topbar-btn { padding: 10px 14px; }
  .tab { padding: 10px 4px; }
  .collapse-toggle { padding: 12px; }
}
</style>
