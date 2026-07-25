<script setup lang="ts">
/**
 * AppHeader — 顶部导航栏
 * 默认折叠(40px)，悬停展开(60px)，向下滚动超过80px隐藏，向上滚动恢复。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import NotificationBell from '@/components/NotificationBell.vue'

defineOptions({ name: 'AppHeader' })

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
    :class="{ collapsed: !isHovered, hidden: isScrollHidden }"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div class="topbar-left">
      <button
        v-if="!isMobile"
        class="topbar-btn sidebar-toggle"
        @click="emit('toggle-sidebar')"
        :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
      >
        <i class="pi pi-bars" />
      </button>
      <span class="topbar-brand">PilotStd</span>
      <span class="topbar-title" v-show="isHovered">{{ pageTitle }}</span>
    </div>
    <div class="topbar-right" v-show="isHovered">
      <!-- 通知铃铛 -->
      <NotificationBell />
      <!-- 主题切换 -->
      <button
        class="topbar-btn theme-btn"
        @click="emit('toggle-theme')"
        :title="isDark ? '切换亮色主题' : '切换暗色主题'"
      >
        <i :class="isDark ? 'pi pi-sun' : 'pi pi-moon'" />
      </button>
      <!-- 用户信息 -->
      <span class="user-tag" v-if="username">
        <i class="pi pi-user" />
        <span class="hide-mobile">{{ username }}</span>
      </span>
      <!-- 退出 -->
      <button class="topbar-btn logout-btn" @click="emit('logout')" title="退出登录">
        <i class="pi pi-sign-out" />
        <span class="hide-mobile">退出</span>
      </button>
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

/* 暗色主题下的顶部导航栏（dark + blue） */
:root[data-theme="dark"] .topbar,
:root[data-theme="blue"] .topbar {
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

/* 响应式 — 平板/移动端隐藏文字 */
@media (max-width: 1023px) {
  .topbar { padding: 0 16px; }
  .hide-mobile { display: none; }
}

@media (max-width: 767px) {
  .topbar {
    height: 56px;
    padding: 0 12px;
  }
  .topbar-brand { font-size: 16px; }
  .topbar-title { font-size: 13px; padding-left: 12px; }
  .topbar-btn { padding: 6px 10px; }
  .topbar-btn i { font-size: 15px; }
}

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  .topbar-btn { padding: 10px 14px; }
}

/* 顶部栏折叠态：默认收缩至40px */
.topbar.collapsed {
  height: 40px;
  padding: 0 16px;
}
.topbar.collapsed .topbar-brand {
  font-size: 15px;
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
