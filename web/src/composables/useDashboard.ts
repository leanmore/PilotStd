/**
 * useDashboard — 仪表盘布局状态（模块级单例）
 *
 * 遵循 useUserPreferences 模式：ref 在模块顶层声明，
 * 所有调用者共享同一实例。HomeView 负责初始化，
 * AppLayout 的悬浮菜单消费 isLocked / availableCards。
 */
import { ref, computed, type Component, markRaw } from 'vue'
import http from '@/api/http'
import { useAppStore } from '@/stores/app'
import { getUserItem, setUserItem, migrateLegacyPreferences } from '@/lib/userStorage'
import StatsCard from '@/components/dashboard/widgets/StatsCard.vue'
import AdapterStatusAnnounceCard from '@/components/dashboard/widgets/AdapterStatusAnnounceCard.vue'
import AdapterStatusQueryCard from '@/components/dashboard/widgets/AdapterStatusQueryCard.vue'
import RecentAnnounceCard from '@/components/dashboard/widgets/RecentAnnounceCard.vue'
import PendingItemsCard from '@/components/dashboard/widgets/PendingItemsCard.vue'
import SystemInfoCard from '@/components/dashboard/widgets/SystemInfoCard.vue'
import QuickActionsCard from '@/components/dashboard/widgets/QuickActionsCard.vue'
import TaskTrendCard from '@/components/dashboard/widgets/TaskTrendCard.vue'
import SystemLogCard from '@/components/dashboard/widgets/SystemLogCard.vue'

// ── 常量 ──
const LAYOUT_STORAGE_KEY = 'dashboard_layout'

const CARD_REGISTRY: Record<string, { label: string; zhName?: string; w: number; h: number }> = {
  stats: { label: '核心统计', w: 4, h: 6 },
  sysInfo: { label: '系统状态', w: 4, h: 6 },
  quickActions: { label: '快捷操作', w: 4, h: 6 },
  announceAdapter: { label: '公告适配器', w: 6, h: 8 },
  queryAdapter: { label: '查询适配器', zhName: '查询适配器集群', w: 8, h: 10 },
  recentAnnounce: { label: '最新公告', w: 6, h: 8 },
  pending: { label: '待确认标准', w: 6, h: 8 },
  trend: { label: '标准库构成', w: 4, h: 8 },
  sysLog: { label: '系统日志', w: 8, h: 8 },
}

const COMPONENT_MAP: Record<string, Component> = {
  stats: markRaw(StatsCard),
  sysInfo: markRaw(SystemInfoCard),
  quickActions: markRaw(QuickActionsCard),
  announceAdapter: markRaw(AdapterStatusAnnounceCard),
  queryAdapter: markRaw(AdapterStatusQueryCard),
  recentAnnounce: markRaw(RecentAnnounceCard),
  pending: markRaw(PendingItemsCard),
  trend: markRaw(TaskTrendCard),
  sysLog: markRaw(SystemLogCard),
}

const DEFAULT_LAYOUT = [
  { i: 'stats', x: 0, y: 0, w: 4, h: 6 },
  { i: 'sysInfo', x: 4, y: 0, w: 4, h: 6 },
  { i: 'quickActions', x: 8, y: 0, w: 4, h: 6 },
  { i: 'announceAdapter', x: 0, y: 6, w: 6, h: 8 },
  { i: 'queryAdapter', x: 6, y: 6, w: 8, h: 10 },
]

// ── 模块级共享状态 ──
const layout = ref<any[]>([])
const isLocked = ref(true)

// ── 私有变量 ──
let saveTimer: ReturnType<typeof setTimeout> | null = null
let fetchVersion = 0  // 竞态防护版本号

// ── 计算属性 ──
const availableCards = computed(() => {
  const currentKeys = new Set(layout.value.map((l: any) => l.i))
  return Object.entries(CARD_REGISTRY)
    .filter(([key]) => !currentKeys.has(key))
    .map(([key, val]) => ({ key, label: val.label }))
})

// ── 方法 ──

function hydrateLayout(rawLayout: any[]) {
  return rawLayout
    .map((item: any) => ({
      ...item,
      component: COMPONENT_MAP[item.i],
      zhName: CARD_REGISTRY[item.i]?.zhName,
    }))
    .filter((item: any) => item.component)
}

async function fetchLayout() {
  const version = ++fetchVersion
  const store = useAppStore()
  const uid = store.userId

  // 兜底迁移：覆盖"PR-B 部署前已登录用户刷新"场景，幂等无开销
  if (uid) migrateLegacyPreferences(uid)

  // 1. 优先读本地缓存（用户隔离 key）
  let hasLocal = false
  if (uid) {
    const cached = getUserItem(uid, LAYOUT_STORAGE_KEY)
    if (cached) {
      try {
        const parsed = JSON.parse(cached)
        if (Array.isArray(parsed) && parsed.length > 0) {
          layout.value = hydrateLayout(parsed)
          hasLocal = true
        }
      } catch { /* ignore */ }
    }
  }

  // 2. 异步拉取服务器配置（仅成功且有效时才覆盖本地）
  try {
    const res = await http.get('/user/preferences/layout:dashboard')
    if (fetchVersion !== version) return
    const raw = res.data?.value   // 后端已 json.loads，value 直接是布局数组
    if (Array.isArray(raw) && raw.length > 0) {
      layout.value = hydrateLayout(raw)
      if (uid) setUserItem(uid, LAYOUT_STORAGE_KEY, JSON.stringify(raw))
      return
    }
  } catch { /* 服务器不可用，继续使用本地缓存 */ }
  if (fetchVersion !== version) return

  // 3. 无任何数据 → 默认布局
  if (!hasLocal) resetLayout()
}

async function saveLayoutToServer(newLayout?: any[]) {
  const source = newLayout || layout.value
  const payload = source.map(({ i, x, y, w, h }: any) => ({ i, x, y, w, h }))

  // 先写本地缓存（用户隔离），server 失败不影响本地持久化
  const store = useAppStore()
  if (store.userId) {
    setUserItem(store.userId, LAYOUT_STORAGE_KEY, JSON.stringify(payload))
  }

  try {
    await http.put('/user/preferences/layout:dashboard', { value: payload })
  } catch {
    console.warn('布局保存到服务器失败，已保留本地缓存')
  }
}

function handleLayoutUpdated(newLayout: any[]) {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveLayoutToServer(newLayout), 500)
}

function toggleLayoutLock() {
  isLocked.value = !isLocked.value
  if (isLocked.value) saveLayoutToServer()
}

function addCard(key: string) {
  const meta = CARD_REGISTRY[key]
  if (!meta) return
  layout.value.push({
    i: key, x: 0, y: 0, w: meta.w, h: meta.h,
    component: COMPONENT_MAP[key],
    zhName: meta.zhName,
  })
}

function removeCard(key: string) {
  layout.value = layout.value.filter((item: any) => item.i !== key)
}

function resetLayout() {
  layout.value = hydrateLayout(JSON.parse(JSON.stringify(DEFAULT_LAYOUT)))
}

// ── 导出 ──
export function useDashboard() {
  return {
    layout,
    isLocked,
    availableCards,
    fetchLayout,
    toggleLayoutLock,
    addCard,
    removeCard,
    resetLayout,
    hydrateLayout,
    handleLayoutUpdated,
    saveLayoutToServer,
  }
}
