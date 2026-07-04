<script setup lang="ts">
defineOptions({ name: 'RecentAnnounceCard' })
import { ref, onMounted } from 'vue'
import { getAnnounceResults } from '@/api'

const list = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const data = await getAnnounceResults()
    list.value = (data.results || []).slice(0, 6)
  } catch { list.value = [] }
  finally { loading.value = false }
})
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-bell" /></div>
        <div>
          <div class="header-title">最新公告</div>
          <div class="header-sub">实时推送</div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="empty">加载中...</div>
    <div v-else-if="!list.length" class="empty">暂无新公告</div>

    <div v-else class="timeline">
      <div v-for="(item, idx) in list" :key="item.standard_number || item.std_code || idx" class="tl-item">
        <div class="tl-dot" :class="{ 'tl-dot-active': idx === 0 }" />
        <div class="tl-line" v-if="idx !== list.length - 1" />
        <div class="tl-content">
          <div class="tl-title">{{ item.standard_number || item.std_code || '无标题' }}</div>
          <div class="tl-meta">{{ item.standard_name || item.std_name || '' }}</div>
        </div>
      </div>
    </div>
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
  width: 34px; height: 34px; border-radius: var(--radius-sm); background: rgba(245,158,11,0.12);
  display: flex; align-items: center; justify-content: center; color: var(--warning); font-size: 16px;
}
.header-title { font-size: 13px; font-weight: 700; color: var(--text-heading); }
.header-sub { font-size: 10px; color: var(--text-dim); }

.timeline { flex: 1; display: flex; flex-direction: column; gap: 0; overflow-y: auto; padding-left: 8px; }
.tl-item { display: flex; position: relative; padding: 8px 0 8px 20px; }
.tl-dot {
  position: absolute; left: 0; top: 12px; width: 8px; height: 8px; border-radius: 50%;
  background: var(--border); border: 2px solid var(--surface); z-index: 1;
}
.tl-dot-active { background: var(--primary); box-shadow: 0 0 6px rgba(99,102,241,0.5); }
.tl-line {
  position: absolute; left: 3.5px; top: 20px; bottom: -8px; width: 1px; background: var(--border-light);
}
.tl-content { flex: 1; min-width: 0; }
.tl-title {
  font-size: 12px; font-weight: 600; color: var(--text-heading); font-family: var(--mono);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tl-meta {
  font-size: 11px; color: var(--text-dim); margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 30px 0; flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
