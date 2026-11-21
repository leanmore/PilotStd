<script setup lang="ts">
defineOptions({ name: 'AdapterStatusAnnounceCard' })
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import Button from 'primevue/button'

const { t } = useI18n()

interface AdapterStatus {
  name: string; status: string; frozen_until: string | null
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
    const r = await http.get('/adapter/status', { params: { type: 'announcement' }, routeTag: '/' })
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

function fullName(n: string): string {
  const map: Record<string, string> = { gb: t('dashboard.announce_adapter.type.gb'), hb: t('dashboard.announce_adapter.type.hb'), db: t('dashboard.announce_adapter.type.db') }
  return map[n] || n.toUpperCase()
}

function iconClass(a: AdapterStatus): string {
  if (a.status === 'frozen') return 'icon-frozen'
  if (a.status === 'cooldown') return 'icon-cooldown'
  return 'icon-ok'
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
  <div class="announce-root">
    <!-- Header -->
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-shield" /></div>
        <div>
          <div class="header-title">{{ t('dashboard.card.announceAdapter') }}</div>
          <div class="header-sub">{{ t('dashboard.announce_adapter.subtitle', { n: adapters.length }) }}</div>
        </div>
      </div>
      <Button icon="pi pi-refresh" size="small" severity="secondary" text rounded :loading="loading" @click="loadStatus" />
    </div>

    <p v-if="error" class="err">{{ error }}</p>

    <!-- 垂直列表模式 -->
    <div v-if="adapters.length" class="list">
      <div v-for="a in adapters" :key="a.name" class="row"
           :class="{ frozen: a.status === 'frozen', cooldown: a.status === 'cooldown' }">
        <!-- 左侧：名称块 -->
        <div class="row-icon" :class="iconClass(a)">
          {{ a.name.toUpperCase() }}
        </div>
        <div class="row-info">
          <span class="row-name">{{ fullName(a.name) }}</span>
          <span class="row-code">{{ a.name }}</span>
          <div class="row-health" :title="healthText(a)">
            <span class="health-dot" :class="healthDotClass(a)" />
            <span class="health-time">{{ healthText(a) }}</span>
          </div>
        </div>
        <!-- 右侧：状态指示 -->
        <div class="row-status">
          <template v-if="a.status === 'normal'">
            <span class="mp-dot-success" />
            <span class="status-text-ok">{{ t('dashboard.common.normal') }}</span>
          </template>
          <template v-else-if="a.status === 'cooldown'">
            <span class="mp-dot-warning" />
            <span class="status-text-warn">{{ t('dashboard.announce_adapter.cooling', { n: a.remaining_seconds }) }}</span>
          </template>
          <template v-else>
            <span class="mp-dot-danger" />
            <span class="status-text-err">{{ t('dashboard.announce_adapter.frozen', { n: a.remaining_seconds }) }}</span>
          </template>
        </div>
        <!-- 异常数据 -->
        <div v-if="a.fail_streak > 0" class="row-warn" :title="t('dashboard.announce_adapter.freeze_tip', { n: a.freeze_count, m: a.fail_streak })">
          <i class="pi pi-exclamation-triangle" />
        </div>
      </div>
    </div>
    <p v-else-if="!loading" class="empty">{{ t('common.no_data') }}</p>
  </div>
</template>

<style scoped>
.announce-root {
  height: 100%; box-sizing: border-box; padding: var(--space-14);
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: var(--space-10);
}

/* Header */
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: var(--space-10); }
.header-icon {
  width: 34px; height: var(--icon-tile-md); border-radius: var(--radius-sm); background: var(--primary-bg);
  display: flex; align-items: center; justify-content: center; color: var(--primary); font-size: var(--font-size-16);
}
.header-title { font-size: var(--font-size-13); font-weight: var(--font-weight-bold); color: var(--text-heading); }
.header-sub { font-size: var(--font-size-10); color: var(--text-dim); }

/* 列表 */
.list { flex: 1; display: flex; flex-direction: column; gap: var(--space-6); overflow-y: auto; }
.row {
  display: flex; align-items: center; gap: var(--space-10); padding: var(--space-10) var(--space-12);
  background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
  transition: all var(--transition);
}
.row:hover { border-color: var(--primary-border); background: var(--primary-bg); }
/* TODO: [Design Debt] rgba(239,68,68,0.04) 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] rgba(239,68,68,0.25) 无精确令牌，暂不替换，待定令牌后统一处理 */
.row.frozen { border-color: rgba(239,68,68,0.25); background: rgba(239,68,68,0.04); }
/* TODO: [Design Debt] rgba(245,158,11,0.04) 无精确令牌，暂不替换，待定令牌后统一处理 */
/* TODO: [Design Debt] rgba(245,158,11,0.25) 无精确令牌，暂不替换，待定令牌后统一处理 */
.row.cooldown { border-color: rgba(245,158,11,0.25); background: rgba(245,158,11,0.04); }

.row-icon {
  /* TODO: [Design Debt] 36px 无精确令牌，暂不替换，待定令牌后统一处理 */
  width: 36px; height: 36px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: var(--font-size-11); font-weight: var(--font-weight-extrabold); font-family: var(--mono); flex-shrink: 0;
}
.icon-ok { background: var(--primary-bg); color: var(--primary); }
.icon-frozen { background: var(--danger-bg); color: var(--danger); }
.icon-cooldown { background: var(--warning-bg); color: var(--warning); }

.row-info { flex: 1; min-width: 0; }
.row-name { font-size: var(--font-size-12); font-weight: var(--font-weight-semibold); color: var(--text-heading); display: block; }
.row-code { font-size: var(--font-size-10); color: var(--text-dim); font-family: var(--mono); }

/* 健康检查指示 */
.row-health { display: flex; align-items: center; gap: var(--space-4); font-size: var(--font-size-9); color: var(--text-dim); margin-top: var(--space-2); }
/* TODO: [Design Debt] 6px 无精确令牌，暂不替换，待定令牌后统一处理 */
.health-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.health-up { background: var(--success); }
.health-down { background: var(--danger); }
.health-none { background: var(--border-light, #ccc); }
.health-time { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.row-status { display: flex; align-items: center; gap: var(--space-6); flex-shrink: 0; }
.status-text-ok { font-size: var(--font-size-11); color: var(--success); font-weight: var(--font-weight-medium); }
.status-text-err { font-size: var(--font-size-11); color: var(--danger); font-weight: var(--font-weight-medium); }
.status-text-warn { font-size: var(--font-size-11); color: var(--warning); font-weight: var(--font-weight-medium); }

.row-warn { color: var(--warning); font-size: var(--font-size-13); cursor: help; flex-shrink: 0; }

.empty { color: var(--text-dim); font-size: var(--font-size-12); text-align: center; padding: var(--space-20) 0; }
.err { color: var(--danger); font-size: var(--font-size-12); }
</style>
