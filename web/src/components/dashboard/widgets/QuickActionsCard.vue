<script setup lang="ts">
defineOptions({ name: 'QuickActionsCard' })
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import http from '@/api/http'

const { t } = useI18n()
const router = useRouter()
const store = useAppStore()
const scanning = ref(false)
const scanMsg = ref('')
const scanErr = ref(false)

// #49: 动作型 handler 注册表（显式 Map，禁止 eval / 动态 import）
const actionHandlers: Record<string, () => Promise<void>> = {
  scanAndIndex,
}

async function scanAndIndex() {
  scanning.value = true
  try {
    const r = await http.post('/scan-and-index')
    scanMsg.value = `扫描完成，入库 ${r.data?.indexed ?? 0} 条标准`
    scanErr.value = false
  } catch (e: any) {
    scanMsg.value = e.response?.data?.error || '扫描失败'
    scanErr.value = true
  } finally {
    scanning.value = false
    setTimeout(() => { scanMsg.value = '' }, 4000)
  }
}

function handleActionClick(action: { type: string; to?: string; handler?: string }) {
  if (action.type === 'action' && action.handler) {
    const fn = actionHandlers[action.handler]
    if (fn) { fn(); return }
  }
  if (action.to) {
    router.push(action.to)
  }
}

// #49: 从路由 meta 动态生成快捷操作，替代硬编码数组
// TODO: Remove fallback after #49 verification - deadline 2026-08-09
const actions = computed(() => {
  const routes = router.getRoutes() as any[]
  const items = routes
    .filter((r: any) => r.meta.showInQuickActions)
    .filter((r: any) => !r.meta.permission || r.meta.permission === store.role || store.role === 'admin')
    .sort((a: any, b: any) => (a.meta.quickActionOrder || 99) - (b.meta.quickActionOrder || 99))
    .map((r: any) => {
      // 翻译 titleKey，翻译缺失时降级到 meta.title 或路径
      let label: string
      if (r.meta.titleKey) {
        const translated = t(r.meta.titleKey)
        label = translated !== r.meta.titleKey ? translated : (r.meta.title || r.path)
      } else {
        label = r.meta.title || r.path
      }
      return {
        label,
        iconClass: r.meta.icon || 'pi pi-circle',
        color: r.meta.color || 'var(--text-dim)',
        to: r.path.startsWith('/__action/') ? undefined : r.path,
        type: r.meta.quickActionType || 'navigation',
        handler: r.meta.handler,
      }
    })

  // Fallback: 若路由 meta 未正确配置，回退到旧硬编码列表
  if (items.length === 0) {
    return [
      { label: '任务', iconClass: 'pi pi-play', color: 'var(--primary)', to: '/task', type: 'navigation' },
      { label: '整理', iconClass: 'pi pi-folder', color: 'var(--warning)', to: '/organize', type: 'navigation' },
      { label: '待处理', iconClass: 'pi pi-hourglass', color: 'var(--info)', to: '/pending', type: 'navigation' },
      { label: '公告', iconClass: 'pi pi-megaphone', color: 'var(--success)', to: '/announce', type: 'navigation' },
      { label: '扫描入库', iconClass: 'pi pi-cloud-upload', color: '#ec4899', type: 'action', handler: 'scanAndIndex' },
    ]
  }
  return items
})

const isLoading = (a: any) =>
  a.type === 'action' && a.handler === 'scanAndIndex' && scanning.value
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-bolt" /></div>
        <span class="header-title">快捷操作</span>
      </div>
    </div>

    <div class="grid">
      <div
        v-for="a in actions" :key="a.label"
        class="btn" :class="{ disabled: isLoading(a) }"
        @click="handleActionClick(a)"
      >
        <i :class="['icon', a.iconClass]" :style="{ color: a.color }" />
        <span class="label">{{ isLoading(a) ? '扫描中…' : a.label }}</span>
      </div>
    </div>
    <div v-if="scanMsg" class="scan-msg" :class="{ error: scanErr }">{{ scanMsg }}</div>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: 14px;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: 10px;
}
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon {
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(139,92,246,0.12);
  display: flex; align-items: center; justify-content: center; color: #8b5cf6; font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }

.grid { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.btn {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
  cursor: pointer; transition: all var(--transition); user-select: none;
}
.btn:hover { border-color: var(--primary-border); background: var(--primary-bg); transform: translateY(-1px); }
.btn:active { transform: scale(0.97); }
.btn.disabled { opacity: 0.5; pointer-events: none; }
.icon { font-size: 22px; }
.label { font-size: 11px; font-weight: 600; color: var(--text-heading); }
.scan-msg { font-size: 11px; color: var(--success); text-align: center; margin-top: 4px; }
.scan-msg.error { color: var(--danger); }
</style>
