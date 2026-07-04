<script setup lang="ts">
defineOptions({ name: 'AdapterStatusAnnounceCard' })
import { ref, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import Button from 'primevue/button'

interface AdapterStatus {
  name: string; status: string; frozen_until: string | null
  remaining_seconds: number; freeze_count: number; fail_streak: number
}

const adapters = ref<AdapterStatus[]>([])
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setInterval> | null = null

async function loadStatus() {
  loading.value = true
  try {
    const r = await http.get('/adapter/status', { params: { type: 'announcement' } })
    adapters.value = r.data.adapters; error.value = ''
  } catch { error.value = '加载失败' }
  finally { loading.value = false }
}

function tick() {
  let anyFrozen = false
  for (const a of adapters.value) {
    if (a.status === 'frozen' && a.remaining_seconds > 0) { a.remaining_seconds--; anyFrozen = true }
  }
  if (!anyFrozen && adapters.value.some(a => a.status === 'frozen')) loadStatus()
}

function fullName(n: string): string {
  const map: Record<string, string> = { gb: '国家标准公告', hb: '行业标准公告', db: '地方标准公告' }
  return map[n] || n.toUpperCase()
}

onMounted(() => { loadStatus(); timer = setInterval(tick, 1000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
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
      <div v-for="a in adapters" :key="a.name" class="row" :class="{ frozen: a.status === 'frozen' }">
        <!-- 左侧：名称块 -->
        <div class="row-icon" :class="a.status === 'frozen' ? 'icon-frozen' : 'icon-ok'">
          {{ a.name.toUpperCase() }}
        </div>
        <div class="row-info">
          <span class="row-name">{{ fullName(a.name) }}</span>
          <span class="row-code">{{ a.name }}</span>
        </div>
        <!-- 右侧：状态指示 -->
        <div class="row-status">
          <template v-if="a.status === 'normal'">
            <span class="mp-dot-success" />
            <span class="status-text-ok">正常</span>
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

.row-icon {
  width: 36px; height: 36px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; font-family: var(--mono); flex-shrink: 0;
}
.icon-ok { background: rgba(99,102,241,0.1); color: var(--primary); }
.icon-frozen { background: rgba(239,68,68,0.12); color: var(--danger); }

.row-info { flex: 1; min-width: 0; }
.row-name { font-size: 12px; font-weight: 600; color: var(--text-heading); display: block; }
.row-code { font-size: 10px; color: var(--text-dim); font-family: var(--mono); }

.row-status { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.status-text-ok { font-size: 11px; color: #16a34a; font-weight: 500; }
.status-text-err { font-size: 11px; color: var(--danger); font-weight: 500; }

.row-warn { color: var(--warning); font-size: 13px; cursor: help; flex-shrink: 0; }

.empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 20px 0; }
.err { color: var(--danger); font-size: 12px; }
</style>
