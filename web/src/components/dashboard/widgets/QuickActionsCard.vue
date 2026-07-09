<script setup lang="ts">
defineOptions({ name: 'QuickActionsCard' })
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/http'

const router = useRouter()
const scanning = ref(false)
const scanMsg = ref('')
const scanErr = ref(false)

const actions = [
  { label: '任务流水线', iconClass: 'pi pi-play', color: '#6366f1', to: '/task' },
  { label: '文件管理', iconClass: 'pi pi-folder', color: '#f59e0b', to: '/organize' },
  { label: '待确认清单', iconClass: 'pi pi-hourglass', color: '#3b82f6', to: '/pending' },
  { label: '公告检查', iconClass: 'pi pi-megaphone', color: '#10b981', to: '/announce' },
]

async function scanAndIndex() {
  scanning.value = true
  try {
    const r = await http.post('/scan-and-index')
    const count = r.data?.indexed ?? 0
    scanMsg.value = `扫描完成，入库 ${count} 条标准`
    scanErr.value = false
  } catch (e: any) {
    scanMsg.value = e.response?.data?.error || '扫描失败'
    scanErr.value = true
  } finally {
    scanning.value = false
    setTimeout(() => { scanMsg.value = '' }, 4000)
  }
}
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
        v-for="a in actions" :key="a.to"
        class="btn" @click="router.push(a.to)"
      >
        <i :class="['icon', a.iconClass]" :style="{ color: a.color }" />
        <span class="label">{{ a.label }}</span>
      </div>
      <div class="btn" :class="{ disabled: scanning }" @click="scanAndIndex">
        <i class="icon pi pi-cloud-upload" style="color: #ec4899" />
        <span class="label">{{ scanning ? '扫描中…' : '扫描入库' }}</span>
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
