// web/src/composables/useAppLayout.ts
/**
 * 应用主布局的组合式逻辑（T-41 前端子批 6(3/3)：从 `AppLayout.vue` 抽出，守 G-010）。
 *
 * **为什么抽 composable**：布局编排（响应式断点、侧边栏折叠、导航项生成、悬浮工作台与无障碍键盘处理）
 * 与模板/样式混在一个 SFC 里会越过 G-010 的有效行警戒线；抽出后 `.vue` 只保留「装配 + 模板 + 样式」。
 *
 * **生命周期与副作用（与拆分前逐字一致）**：
 * · `onMounted`：恢复侧边栏折叠偏好 + 注册 `resize` 监听 + 注册 `click`（点外关闭菜单）；
 * · `onUnmounted`：**成对**移除 `resize` 与 `click` 监听（无泄漏）；
 * · `watch(() => route.path, closeMenu)`：路由切换自动关闭菜单（**不**使用 `onBeforeRouteUpdate`）。
 * 这些钩子在本函数内注册；由于本函数在 `setup()` 中被调用一次，注册时机与拆分前**完全相同**，
 * 因此"Layout 只挂载一次"或"因路由配置变化而重建"两种情形下的行为均不变。
 *
 * **状态作用域（全局 UI 状态流转自查的结论）**：
 * · **应用级**（来自 Pinia）：`store.theme`/`store.role`/`store.username`（`useAppStore`）、
 *   侧边栏折叠的**持久化**（`usePreferencesStore().set('sidebar_collapsed', …)` ⇒ 落后端偏好）；
 * · **组件级**（本函数内 `ref`）：`isDesktop/isTablet/isMobile`、`sidebarCollapsed` 的**内存值**、
 *   `menuOpen`、悬浮按钮坐标 `(x, y)`（来自 `useFloatingDrag`）。每次 Layout 重建都会重新初始化，
 *   但**折叠状态会从偏好恢复**（`loadSidebarState`）⇒ 重建不丢用户选择；无重复订阅（监听器成对注册/注销）。
 *
 * **契约（对外接口零变化）**：本函数返回模板所需的**全部**名字（`ref`/`computed` 引用本身，不解包）；
 * 组件模板的**默认插槽 `<slot />` 与透传方式逐字未改**（无具名/作用域插槽，故无插槽契约风险）。
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import { usePreferencesStore } from '@/stores/preferences'
import { useDashboard } from '@/composables/useDashboard'
import { useFloatingDrag } from '@/composables/useFloatingDrag'
import http from '@/api/http'

// ── 导航项配置 ──
// #49: navItems 改为 computed，从路由 meta 动态生成
// 2026-09-27 #49 收尾复核（探针实测真实 router）：21 条路由记录中 showInSidebar = 11，
// navItems 实测 role 空/guest/未知 → 10 项、user/admin → 11 项，**恒非空**；
// 且全库无 router.addRoute（纯静态路由），故删除原"空列表兜底"分支及其过期 TODO（deadline 2026-08-09）。
interface SidebarRoute {
  meta: {
    showInSidebar?: boolean
    permission?: string
    sidebarOrder?: number
    titleKey?: string
    title?: string
    icon?: string
  }
  path: string
}

export function useAppLayout() {
  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const store = useAppStore()

  const navItems = computed(() => {
    const items = (router.getRoutes() as SidebarRoute[])
      .filter((r) => r.meta.showInSidebar && !r.path.startsWith('/__action/'))
      .filter((r) => !r.meta.permission || r.meta.permission === store.role || store.role === 'admin')
      .sort((a, b) => (a.meta.sidebarOrder || 99) - (b.meta.sidebarOrder || 99))
      .map((r) => ({
        label: r.meta.titleKey ? t(r.meta.titleKey) : r.meta.title || r.path,
        icon: r.meta.icon || 'pi pi-circle',
        to: r.path,
      }))
    return items
  })

  // ── 响应式断点（组件级状态：随 Layout 重建而重新初始化，属预期）──
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
    } catch {
      /* 未登录时使用默认值 */
    }
  }

  function onResize() {
    isDesktop.value = window.innerWidth >= 1024
    isTablet.value = window.innerWidth >= 768 && window.innerWidth < 1024
    isMobile.value = window.innerWidth < 768
    // 移动端始终折叠（避免覆盖内容），桌面/平板保持用户选择
    if (isMobile.value) sidebarCollapsed.value = true
  }

  onMounted(() => {
    loadSidebarState()
    window.addEventListener('resize', onResize)
  })
  onUnmounted(() => window.removeEventListener('resize', onResize))

  // ── 计算属性 ──
  const pageTitle = computed(() => {
    const item = navItems.value.find((n) => n.to === route.path)
    return item?.label ?? 'PilotStd'
  })

  const isDark = computed(() => store.theme === 'dark')

  // ── 事件处理 ──
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    usePreferencesStore()
      .set('sidebar_collapsed', sidebarCollapsed.value)
      .catch(() => {})
  }
  function toggleTheme() {
    store.theme = isDark.value ? 'light' : 'dark'
  }
  async function logout() {
    try {
      await http.post('/logout', undefined, { skipGlobalAuthRedirect: true })
    } catch {
      /* 即使服务端登出失败也清除本地状态 */
    }
    store.clearUser()
    router.push('/login')
  }

  // ── 悬浮工作台按钮（统一入口，路由动态切换）──
  const { availableCards, addCard, resetLayout } = useDashboard()
  const { x, y, onPointerDown, onPointerMove, onPointerUp, consumeClick } = useFloatingDrag()
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

  /** 悬浮按钮统一点击入口：先吞掉拖拽触发的 click，再按路由态分发原行为 */
  function onFloatingButtonClick() {
    if (consumeClick()) return
    if (isAnnounceDetail.value) router.back()
    else if (isHomeRoute.value) toggleMenu()
    else router.push('/')
  }

  function onClickOutside(e: MouseEvent) {
    const menu = document.querySelector('.floating-workspace-menu')
    if (menu && !menu.contains(e.target as Node)) closeMenu()
  }

  function onMenuKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      closeMenu()
      return
    }
    if (e.key === 'Tab') {
      const items = document
        .getElementById(dropdownId)
        ?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])')
      if (!items || items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }

  // 增强 #1：路由切换自动关闭菜单
  watch(() => route.path, () => closeMenu())

  // 点外关闭菜单（与 resize 监听**成对**注册/注销）
  onMounted(() => document.addEventListener('click', onClickOutside))
  onUnmounted(() => document.removeEventListener('click', onClickOutside))

  // ── 返回模板所需的全部名字（引用不解包 ⇒ 响应式照常）──
  return {
    t,
    route,
    store,
    navItems,
    isDesktop,
    isTablet,
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
    consumeClick,
    menuOpen,
    triggerBtnId,
    dropdownId,
    isHomeRoute,
    isAnnounceDetail,
    toggleMenu,
    closeMenu,
    onFloatingButtonClick,
    onMenuKeydown,
  }
}
