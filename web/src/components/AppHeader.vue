<script setup lang="ts">
/**
 * AppHeader — 顶部导航栏
 * 默认折叠(40px)，悬停展开(60px)，向下滚动超过80px隐藏，向上滚动恢复。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import NotificationBell from '@/components/NotificationBell.vue'
import AppButton from '@/components/ui/AppButton.vue'

defineOptions({ name: 'AppHeader' })

const { t } = useI18n()

defineProps<{
  isMobile: boolean
  sidebarCollapsed: boolean
  pageTitle: string
  isDark: boolean
  username: string
}>()

const emit = defineEmits<{
  (e: 'toggle-sidebar'): void
  (e: 'toggle-theme'): void
  (e: 'logout'): void
}>()

// ── 悬停展开 / 滚动隐藏 ──
const isHovered = ref(false)
// Popover 打开期间顶栏不能因 mouseleave 收起：否则铃铛被 display:none，弹层会重排到左上角
const notificationOpen = ref(false)
const isScrollHidden = ref(false)
let lastScrollY = 0

function onScroll() {
  const currentScrollY = window.scrollY
  if (currentScrollY > lastScrollY && currentScrollY > 80) {
    isScrollHidden.value = true
  } else {
    isScrollHidden.value = false
  }
  lastScrollY = currentScrollY
}

onMounted(() => {
  lastScrollY = window.scrollY
  window.addEventListener('scroll', onScroll, { passive: true })
})
onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <header
    class="topbar"
    :class="{ collapsed: !isHovered && !notificationOpen, hidden: isScrollHidden }"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div class="topbar-left">
      <AppButton
        v-if="!isMobile"
        class="topbar-btn sidebar-toggle"
        @click="emit('toggle-sidebar')"
        :title="sidebarCollapsed ? t('dashboard.header.expand_sidebar') : t('dashboard.header.collapse_sidebar')"
  size="s"
  type="ghost"
  bare
>
        <i class="pi pi-bars" />
      </AppButton>
      <span class="topbar-brand">PilotStd</span>
      <span class="topbar-title" v-show="isHovered">{{ pageTitle }}</span>
    </div>
    <div class="topbar-right" v-show="isHovered || notificationOpen">
      <!-- 通知铃铛 -->
      <NotificationBell @popover-show="notificationOpen = true" @popover-hide="notificationOpen = false" />
      <!-- 主题切换 -->
      <AppButton
        class="topbar-btn theme-btn"
        @click="emit('toggle-theme')"
        :title="isDark ? t('dashboard.header.to_light') : t('dashboard.header.to_dark')"
  size="s"
  type="ghost"
  bare
>
        <i :class="isDark ? 'pi pi-sun' : 'pi pi-moon'" />
      </AppButton>
      <!-- 用户信息 -->
      <span class="user-tag" v-if="username">
        <i class="pi pi-user" />
        <span class="hide-mobile">{{ username }}</span>
      </span>
      <!-- 退出 -->
      <AppButton class="topbar-btn logout-btn" data-testid="user-menu-logout" @click="emit('logout')" :title="t('dashboard.header.logout_title')"
  size="s"
  type="ghost"
  bare
>
        <i class="pi pi-sign-out" />
        <span class="hide-mobile">{{ t('dashboard.header.logout') }}</span>
      </AppButton>
    </div>
  </header>
</template>

<style scoped>
/* ═══════════════════════════════════════════
   顶部导航栏
   ═══════════════════════════════════════════ */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  /* TODO: [Design Debt] 60px 无精确令牌，暂不替换，待定令牌后统一处理 */
  height: 60px;
  padding: 0 var(--space-24);
  /* TODO: [Design Debt] rgba(255, 255, 255, 0.8) 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  /* TODO: [Design Debt] 0 1px 3px rgba(0, 0, 0, 0.05), 0 4px 12px -4px rgba(0, 0, 0, 0.08) 无精确令牌，暂不替换，待定令牌后统一处理 */
  /* TODO: [Design Debt] 原生阴影与既有 --shadow-* 层级不匹配（半径/扩散/透明度不同），待统一评估（A-52） */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 4px 12px -4px rgba(0, 0, 0, 0.08);
  z-index: 100;
  flex-shrink: 0;
  position: sticky;
  top: 0;
}

/* 暗色主题下的顶部导航栏（dark + blue） */
:root[data-theme="dark"] .topbar,
:root[data-theme="blue"] .topbar {
  /* TODO: [Design Debt] rgba(30, 41, 59, 0.85) 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: rgba(30, 41, 59, 0.85);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-16);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.topbar-brand {
  font-size: var(--font-size-18);
  font-weight: var(--font-weight-extrabold);
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.03em;
}

.topbar-title {
  font-size: var(--font-size-14);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  padding-left: var(--space-16);
  border-left: 2px solid var(--border);
}

.topbar-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-8) var(--space-14);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-size-13);
  font-weight: var(--font-weight-medium);
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
  font-size: var(--font-size-16);
  position: relative;
  z-index: 1;
}
.topbar-btn span {
  position: relative;
  z-index: 1;
}

.theme-btn:hover { color: var(--warning); }
.logout-btn:hover { color: var(--danger); }

.user-tag {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-6) var(--space-12);
  font-size: var(--font-size-13);
  font-weight: var(--font-weight-medium);
  color: var(--text);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.user-tag i { font-size: var(--font-size-14); color: var(--primary); }

/* 响应式 — 平板/移动端隐藏文字 */
@media (max-width: 1023px) {
  .topbar { padding: 0 var(--space-16); }
  .hide-mobile { display: none; }
}

@media (max-width: 767px) {
  .topbar {
    /* TODO: [Design Debt] 56px 无精确令牌，暂不替换，待定令牌后统一处理 */
    height: 56px;
    padding: 0 var(--space-12);
  }
  .topbar-brand { font-size: var(--font-size-16); }
  .topbar-title { font-size: var(--font-size-13); padding-left: var(--space-12); }
  .topbar-btn { padding: var(--space-6) var(--space-10); }
  .topbar-btn i { font-size: var(--font-size-15); }
}

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .topbar-btn { padding: var(--space-10) var(--space-14); }
}

/* 顶部栏折叠态：默认收缩至40px */
.topbar.collapsed {
  /* TODO: [Design Debt] 40px 无精确令牌，暂不替换，待定令牌后统一处理 */
  height: 40px;
  padding: 0 var(--space-16);
}
.topbar.collapsed .topbar-brand {
  font-size: var(--font-size-15);
}

/* 滚动隐藏：完全滑出视口 */
.topbar.hidden {
  transform: translateY(-100%);
}

.topbar {
  transition: height 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
