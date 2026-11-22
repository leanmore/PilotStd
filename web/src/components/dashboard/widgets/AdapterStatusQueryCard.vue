<script setup lang="ts">
defineOptions({ name: 'AdapterStatusQueryCard' })
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import Button from 'primevue/button'

const { t } = useI18n()
const props = defineProps<{ titleKey?: string }>()

interface AdapterStatus {
  name: string; display_name?: string; status: string; frozen_until: string | null
  remaining_seconds: number; freeze_count: number; fail_streak: number
  last_health_check: string | null; health_status: string | null
}

const adapters = ref<AdapterStatus[]>([])
const loading = ref(false)
const error = ref('')
let countdownTimer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadStatus() {
  loading.value = true
  try {
    const r = await http.get('/adapter/status', { params: { type: 'query' }, routeTag: '/' })
    adapters.value = r.data.adapters; error.value = ''
  } catch { error.value = t('dashboard.common.load_failed') }
  finally { loading.value = false }
}

function tick() {
  let anyActive = false
  for (const a of adapters.value) {
    if ((a.status === 'frozen' || a.status === 'cooldown') && a.remaining_seconds > 0) {
      a.remaining_seconds--; anyActive = true
    }
  }
  if (!anyActive && adapters.value.some(a => a.status === 'frozen' || a.status === 'cooldown')) loadStatus()
}

function fullName(a: AdapterStatus): string {
  if (a.display_name) return a.display_name
  if (a.name) return a.name
  return t('dashboard.query_adapter.unknown_site')
}

function healthText(a: AdapterStatus): string {
  if (!a.last_health_check) return t('sites.health_never')
  const ms = Date.now() - new Date(a.last_health_check).getTime()
  const min = Math.max(0, Math.floor(ms / 60000))
  if (min < 60) return t('sites.health_checked_min', { min })
  return t('sites.health_checked_hour', { hour: Math.floor(min / 60) })
}

function healthDotClass(a: AdapterStatus): string {
  if (a.health_status === 'up') return 'health-up'
  if (a.health_status === 'down') return 'health-down'
  return 'health-none'
}

onMounted(() => {
  loadStatus()
  countdownTimer = setInterval(tick, 1000)
  pollTimer = setInterval(loadStatus, 3600000)  // 1 小时周期轮询，对齐后端健康检查间隔
})
onBeforeUnmount(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="query-root">
    <!-- Header -->
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-globe" /></div>
        <div>
          <div class="header-title">{{ t(props.titleKey || 'dashboard.card.queryAdapterTitle') }}</div>
          <div class="header-sub">{{ t('dashboard.query_adapter.nodes', { n: adapters.length }) }}</div>
        </div>
      </div>
      <Button icon="pi pi-refresh" size="small" severity="secondary" text rounded :loading="loading" @click="loadStatus" />
    </div>

    <p v-if="error" class="err">{{ error }}</p>

    <!-- 紧凑网格 -->
    <div v-if="adapters.length" class="grid">
      <div v-for="a in adapters" :key="a.name" class="cell"
           :class="{ frozen: a.status === 'frozen', cooldown: a.status === 'cooldown' }">
        <!-- 状态点 -->
        <div class="cell-dot">
          <span v-if="a.status === 'normal'" class="mp-dot-success" />
          <span v-else-if="a.status === 'cooldown'" class="mp-dot-warning" />
          <span v-else class="mp-dot-danger" />
        </div>
        <!-- 名称 -->
        <div class="cell-name" :title="fullName(a)">{{ a.name }}</div>
        <div class="cell-cn">{{ fullName(a) }}</div>
        <!-- 底部状态条 -->
        <div class="cell-bar">
          <div class="cell-bar-fill"
               :class="a.status === 'normal' ? 'bar-ok' : a.status === 'cooldown' ? 'bar-warn' : 'bar-err'"
               :style="{ width: a.status === 'normal' ? '100%' : '40%' }" />
        </div>
        <!-- 健康检查指示 -->
        <div class="cell-health" :title="healthText(a)">
          <span class="health-dot" :class="healthDotClass(a)" />
          <span class="health-time">{{ healthText(a) }}</span>
        </div>
        <!-- 异常数据 hover 显示 -->
        <div v-if="a.status === 'frozen' || a.status === 'cooldown'" class="cell-overlay">
          <span>{{ a.remaining_seconds }}s</span>
        </div>
      </div>
    </div>
    <p v-else-if="!loading" class="empty">{{ t('common.no_data') }}</p>
  </div>
</template>

<style scoped>
.query-root {
  height: 100%; box-sizing: border-box; padding: var(--space-14);
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: var(--space-10);
}

/* Header */
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: var(--space-10); }
.header-icon {
  width: 34px; height: var(--icon-tile-md); border-radius: var(--radius-sm); background: var(--info-bg);
  display: flex; align-items: center; justify-content: center; color: var(--info); font-size: var(--font-size-16);
}
.header-title { font-size: var(--font-size-13); font-weight: var(--font-weight-bold); color: var(--text-heading); }
.header-sub { font-size: var(--font-size-10); color: var(--text-dim); }

/* 网格 */
.grid {
  flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: var(--space-8); align-content: start; overflow-y: auto;
}
.cell {
  position: relative; display: flex; flex-direction: column; align-items: center; gap: var(--space-4);
  padding: var(--space-14) var(--space-10) var(--space-12); background: var(--surface); border: 1px solid var(--border-light);
  border-radius: var(--radius); transition: all var(--transition); overflow: hidden;
}
/* TODO: [Design Debt] rgba(59,130,246,0.04) 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] rgba(59,130,246,0.3) 无精确令牌，暂不替换，待定令牌后统一处理 */
.cell:hover { border-color: rgba(59,130,246,0.3); background: rgba(59,130,246,0.04); }
/* TODO: [Design Debt] rgba(239,68,68,0.03) 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] rgba(239,68,68,0.2) 无精确令牌，暂不替换，待定令牌后统一处理 */
.cell.frozen { border-color: rgba(239,68,68,0.2); background: rgba(239,68,68,0.03); }
/* TODO: [Design Debt] rgba(245,158,11,0.03) 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] rgba(245,158,11,0.2) 无精确令牌，暂不替换，待定令牌后统一处理 */
.cell.cooldown { border-color: rgba(245,158,11,0.2); background: rgba(245,158,11,0.03); }

.cell-dot { position: absolute; top: 6px; right: 6px; }
.cell-name {
  font-size: var(--font-size-12); font-weight: var(--font-weight-bold); color: var(--text-heading); font-family: var(--mono);
  text-align: center; margin-top: var(--space-4); word-break: break-all;
}
.cell-cn {
  font-size: var(--font-size-10); color: var(--text-dim); text-align: center; word-break: keep-all; line-height: var(--line-height-compact);
}

.cell-bar { width: 100%; height: 3px; background: var(--border-light); border-radius: 2px; overflow: hidden; }
.cell-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
.bar-ok { background: var(--success); }
.bar-err { background: var(--danger); }
.bar-warn { background: var(--warning); }

/* 健康检查指示 */
.cell-health {
  display: flex; align-items: center; justify-content: center; gap: var(--space-4);
  font-size: var(--font-size-9); color: var(--text-dim); width: 100%; overflow: hidden;
}
/* TODO: [Design Debt] 6px 无精确令牌，暂不替换，待定令牌后统一处理 */
.health-dot { width: var(--size-6); height: var(--size-6); border-radius: 50%; flex-shrink: 0; }
.health-up { background: var(--success); }
.health-down { background: var(--danger); }
.health-none { background: var(--border-light, #ccc); }
.health-time { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.cell-overlay {
  /* TODO: [Design Debt] rgba(239,68,68,0.85) 无精确令牌，暂不替换，待定令牌后统一处理 */
  position: absolute; inset: 0; background: rgba(239,68,68,0.85);
  display: flex; align-items: center; justify-content: center;
  /* TODO: [Design Debt] #fff 无精确令牌，暂不替换，待定令牌后统一处理 */
  color: #fff; font-size: var(--font-size-13); font-weight: var(--font-weight-bold); font-family: var(--mono);
  opacity: 0; transition: opacity 0.2s;
}
.cell:hover .cell-overlay { opacity: 1; }

.empty { color: var(--text-dim); font-size: var(--font-size-12); text-align: center; padding: var(--space-20) 0; }
.err { color: var(--danger); font-size: var(--font-size-12); }
</style>
