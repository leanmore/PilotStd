<script setup lang="ts">
defineOptions({ name: 'AdapterStatusQueryCard' })
import { ref, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import Button from 'primevue/button'

const props = defineProps<{ zhName?: string }>()

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
    const r = await http.get('/adapter/status', { params: { type: 'query' } })
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

function fullName(a: AdapterStatus): string {
  if (a.display_name) return a.display_name
  if (a.name) return a.name
  return '未知站点'
}

function healthText(a: AdapterStatus): string {
  if (!a.last_health_check) return '尚未检查'
  const ms = Date.now() - new Date(a.last_health_check).getTime()
  const min = Math.max(0, Math.floor(ms / 60000))
  if (min < 60) return `最后检查：${min} 分钟前`
  return `最后检查：${Math.floor(min / 60)} 小时前`
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
          <div class="header-title">{{ props.zhName || '查询适配器集群' }}</div>
          <div class="header-sub">{{ adapters.length }} 节点</div>
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
    <p v-else-if="!loading" class="empty">暂无数据</p>
  </div>
</template>

<style scoped>
.query-root {
  height: 100%; box-sizing: border-box; padding: 14px;
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: 10px;
}

/* Header */
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon {
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(59,130,246,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--info); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
.header-sub { font-size: 10px; color: var(--text-dim); }

/* 网格 */
.grid {
  flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px; align-content: start; overflow-y: auto;
}
.cell {
  position: relative; display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 14px 10px 12px; background: var(--surface); border: 1px solid var(--border-light);
  border-radius: var(--radius); transition: all var(--transition); overflow: hidden;
}
.cell:hover { border-color: rgba(59,130,246,0.3); background: rgba(59,130,246,0.04); }
.cell.frozen { border-color: rgba(239,68,68,0.2); background: rgba(239,68,68,0.03); }
.cell.cooldown { border-color: rgba(245,158,11,0.2); background: rgba(245,158,11,0.03); }

.cell-dot { position: absolute; top: 6px; right: 6px; }
.cell-name {
  font-size: 12px; font-weight: 700; color: var(--text-heading); font-family: var(--mono);
  text-align: center; margin-top: 4px; word-break: break-all;
}
.cell-cn {
  font-size: 10px; color: var(--text-dim); text-align: center; word-break: keep-all; line-height: 1.3;
}

.cell-bar { width: 100%; height: 3px; background: var(--border-light); border-radius: 2px; overflow: hidden; }
.cell-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
.bar-ok { background: var(--success); }
.bar-err { background: var(--danger); }
.bar-warn { background: var(--warning); }

/* 健康检查指示 */
.cell-health {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  font-size: 9px; color: var(--text-dim); width: 100%; overflow: hidden;
}
.health-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.health-up { background: var(--success); }
.health-down { background: var(--danger); }
.health-none { background: var(--border-light, #ccc); }
.health-time { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.cell-overlay {
  position: absolute; inset: 0; background: rgba(239,68,68,0.85);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 13px; font-weight: 700; font-family: var(--mono);
  opacity: 0; transition: opacity 0.2s;
}
.cell:hover .cell-overlay { opacity: 1; }

.empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 20px 0; }
.err { color: var(--danger); font-size: 12px; }
</style>
