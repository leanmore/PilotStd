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
    const r = await http.get('/adapter/status', { params: { type: 'announcement' } })
    adapters.value = r.data.adapters; error.value = ''
  } catch { error.value = '加载失败' }
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
  const map: Record<string, string> = { gb: '国家标准公告', hb: '行业标准公告', db: '地方标准公告' }
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
          <div class="header-title">公告适配器</div>
          <div class="header-sub">核心链路 · {{ adapters.length }} 节点</div>
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
            <span class="status-text-ok">正常</span>
          </template>
          <template v-else-if="a.status === 'cooldown'">
            <span class="mp-dot-warning" />
            <span class="status-text-warn">冷却 {{ a.remaining_seconds }}s</span>
          </template>
          <template v-else>
            <span class="mp-dot-danger" />
            <span class="status-text-err">冻结 {{ a.remaining_seconds }}s</span>
          </template>
        </div>
        <!-- 异常数据 -->
        <div v-if="a.fail_streak > 0" class="row-warn" :title="`冻结${a.freeze_count}次 / 连续失败${a.fail_streak}次`">
          <i class="pi pi-exclamation-triangle" />
        </div>
      </div>
    </div>
    <p v-else-if="!loading" class="empty">暂无数据</p>
  </div>
</template>

<style scoped>
.announce-root {
  height: 100%; box-sizing: border-box; padding: 14px;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: 10px;
}

/* Header */
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon {
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(99,102,241,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--primary); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
.header-sub { font-size: 10px; color: var(--text-dim); }

/* 列表 */
.list { flex: 1; display: flex; flex-direction: column; gap: 6px; overflow-y: auto; }
.row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius);
  transition: all var(--transition);
}
.row:hover { border-color: var(--primary-border); background: var(--primary-bg); }
.row.frozen { border-color: rgba(239,68,68,0.25); background: rgba(239,68,68,0.04); }
.row.cooldown { border-color: rgba(245,158,11,0.25); background: rgba(245,158,11,0.04); }

.row-icon {
  width: 36px; height: 36px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; font-family: var(--mono); flex-shrink: 0;
}
.icon-ok { background: rgba(99,102,241,0.1); color: var(--primary); }
.icon-frozen { background: rgba(239,68,68,0.12); color: var(--danger); }
.icon-cooldown { background: rgba(245,158,11,0.12); color: var(--warning); }

.row-info { flex: 1; min-width: 0; }
.row-name { font-size: 12px; font-weight: 600; color: var(--text-heading); display: block; }
.row-code { font-size: 10px; color: var(--text-dim); font-family: var(--mono); }

/* 健康检查指示 */
.row-health { display: flex; align-items: center; gap: 4px; font-size: 9px; color: var(--text-dim); margin-top: 2px; }
.health-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.health-up { background: var(--success); }
.health-down { background: var(--danger); }
.health-none { background: var(--border-light, #ccc); }
.health-time { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.row-status { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.status-text-ok { font-size: 11px; color: var(--success); font-weight: 500; }
.status-text-err { font-size: 11px; color: var(--danger); font-weight: 500; }
.status-text-warn { font-size: 11px; color: var(--warning); font-weight: 500; }

.row-warn { color: var(--warning); font-size: 13px; cursor: help; flex-shrink: 0; }

.empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 20px 0; }
.err { color: var(--danger); font-size: 12px; }
</style>
