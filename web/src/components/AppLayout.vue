<script setup lang="ts">
/**
 * AppLayout — 应用主布局（编排层）
 *
 * 职责：响应式断点检测、侧边栏折叠状态管理、子组件编排。
 * Header / Sidebar 已拆分为独立组件。
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import { usePreferencesStore } from '@/stores/preferences'
import { useDashboard } from '@/composables/useDashboard'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

defineOptions({ name: 'AppLayout' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useAppStore()

// ── 导航项配置 ──
// #49: navItems 改为 computed，从路由 meta 动态生成
  // TODO: Remove fallback after #49 verification - deadline 2026-08-09
  const navItems = computed(() => {
    const items = router.getRoutes()
      .filter((r: any) => r.meta.showInSidebar && !r.path.startsWith('/__action/'))
      .filter((r: any) => !r.meta.permission || r.meta.permission === store.role || store.role === 'admin')
      .sort((a: any, b: any) => (a.meta.sidebarOrder || 99) - (b.meta.sidebarOrder || 99))
      .map((r: any) => ({
        label: r.meta.titleKey ? t(r.meta.titleKey) : (r.meta.title || r.path),
        icon: r.meta.icon || 'pi pi-circle',
        to: r.path,
      }))
    if (items.length === 0) {
      return [
        { label: t('nav.home'), icon: 'pi pi-home', to: '/' },
        { label: t('nav.task'), icon: 'pi pi-play', to: '/task' },
        { label: t('nav.organize'), icon: 'pi pi-folder', to: '/organize' },
        { label: t('nav.pending'), icon: 'pi pi-hourglass', to: '/pending' },
        { label: '导入下载', icon: 'pi pi-download', to: '/download/import' },
        { label: t('nav.announce'), icon: 'pi pi-megaphone', to: '/announce' },
        { label: t('nav.notification_logs'), icon: 'pi pi-list', to: '/notification-logs' },
        { label: t('nav.standards_status'), icon: 'pi pi-verified', to: '/standards-status' },
        { label: t('nav.settings'), icon: 'pi pi-cog', to: '/settings' },
      ]
    }
    return items
  })

// ── 响应式断点 ──
const isDesktop = ref(window.innerWidth >= 1024)
const isTablet = ref(window.innerWidth >= 768 && window.innerWidth < 1024)
const isMobile = ref(window.innerWidth < 768)

// 侧边栏折叠 - 从偏好恢复，平板/移动端默认折叠
const sidebarCollapsed = ref(!isDesktop.value)

async function loadSidebarState() {
  try {
    const prefs = usePreferencesStore()
    const all = await prefs.getAll()
    const saved = all.sidebar_collapsed
    if (typeof saved === 'boolean') sidebarCollapsed.value = saved
  } catch { /* 未登录时使用默认值 */ }
}

function onResize() {
  isDesktop.value = window.innerWidth >= 1024
  isTablet.value = window.innerWidth >= 768 && window.innerWidth < 1024
  isMobile.value = window.innerWidth < 768
  // 移动端始终折叠（避免覆盖内容），桌面/平板保持用户选择
  if (isMobile.value) sidebarCollapsed.value = true
}

onMounted(() => { loadSidebarState(); window.addEventListener('resize', onResize) })
onUnmounted(() => window.removeEventListener('resize', onResize))

// ── 计算属性 ──
const pageTitle = computed(() => {
  const item = navItems.value.find((n: any) => n.to === route.path)
  return item?.label ?? 'PilotStd'
})

const isDark = computed(() => store.theme === 'dark')

// ── 事件处理 ──
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  usePreferencesStore().set('sidebar_collapsed', sidebarCollapsed.value).catch(() => {})
}
function toggleTheme() { store.theme = isDark.value ? 'light' : 'dark' }
function logout() { router.push('/login') }

// ── 悬浮工作台按钮（统一入口，路由动态切换）──
const { availableCards, isLocked, addCard, toggleLayoutLock, resetLayout } = useDashboard()
const menuOpen = ref(false)
const triggerBtnId = 'workspace-menu-trigger'
const dropdownId = 'workspace-dropdown'
const isHomeRoute = computed(() => route.path === '/')
const isAnnounceDetail = computed(() => !!(route.params.source && route.params.announceNo))

function toggleMenu() {
  menuOpen.value = !menuOpen.value
  if (menuOpen.value) {
    // 展开后将焦点移至菜单首项
    requestAnimationFrame(() => {
      const first = document.getElementById(dropdownId)?.querySelector<HTMLElement>('[role="menuitem"]')
      first?.focus()
    })
  }
}

function closeMenu() {
  menuOpen.value = false
  // 焦点归还触发按钮
  document.getElementById(triggerBtnId)?.focus()
}

function onClickOutside(e: MouseEvent) {
  const menu = document.querySelector('.floating-workspace-menu')
  if (menu && !menu.contains(e.target as Node)) closeMenu()
}

function onMenuKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') { e.preventDefault(); closeMenu(); return }
  if (e.key === 'Tab') {
    const items = document.getElementById(dropdownId)?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])')
    if (!items || items.length === 0) return
    const first = items[0]; const last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
}

// 增强 #1：路由切换自动关闭菜单
watch(() => route.path, () => closeMenu())

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
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

    <!-- ═══ 全局悬浮按钮（桌面端右下角，路由动态切换） ═══ -->
    <div v-if="!isMobile" class="floating-workspace-menu" :class="{ open: menuOpen }">

      <!-- 模式1：公告详情页 — 返回列表 -->
      <button
        v-if="isAnnounceDetail"
        class="floating-workspace-btn"
        @click="router.back()"
        aria-label="返回列表"
      >
        <i class="pi pi-undo" />
      </button>

      <!-- 模式2：首页 — 展开菜单 -->
      <template v-else-if="isHomeRoute">
        <button
          :id="triggerBtnId"
          class="floating-workspace-btn"
          @click.stop="toggleMenu"
          aria-label="工作台菜单"
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
              <i class="pi pi-plus" /><span>添加 {{ card.label }}</span>
            </button>
            <div v-if="availableCards.length === 0"
                 class="menu-item disabled" role="menuitem" aria-disabled="true">
              <span>所有卡片已添加</span>
            </div>
            <div class="menu-divider" role="separator" />
            <!-- ② 锁定/解锁布局 -->
            <button role="menuitem" class="menu-item" tabindex="0"
                    @click="toggleLayoutLock(); closeMenu()">
              <i :class="isLocked ? 'pi pi-lock-open' : 'pi pi-lock'" />
              <span>{{ isLocked ? '解锁布局' : '锁定布局' }}</span>
            </button>
            <div class="menu-divider" role="separator" />
            <!-- ③ 重置布局 -->
            <button role="menuitem" class="menu-item" tabindex="0"
                    @click="resetLayout(); closeMenu()">
              <i class="pi pi-refresh" />
              <span>重置布局</span>
            </button>
          </div>
        </Transition>
      </template>

      <!-- 模式3：其他页面 — 返回工作台 -->
      <button
        v-else
        class="floating-workspace-btn"
        @click="router.push('/')"
        aria-label="返回工作台"
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
  bottom: 32px;
  right: 24px;
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
