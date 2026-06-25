<script setup lang="ts">
// RecentAnnounceCard.vue — 最近公告列表 Widget（从 HomeView 迁移）
import { ref, onMounted } from 'vue'
import { getAnnounceResults } from '@/api'

const announces = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const data = await getAnnounceResults()
    announces.value = (data.results || []).slice(0, 5)
  } catch {
    // 公告非关键，静默失败
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="announce-widget">
    <div class="widget-header">最近公告</div>
    <template v-if="loading">
      <div v-for="n in 3" :key="n" class="skeleton-item">
        <div class="skeleton-line skeleton-code" />
        <div class="skeleton-line skeleton-name" />
      </div>
    </template>
    <p v-else-if="announces.length === 0" class="empty">暂无数据</p>
    <div v-for="a in announces" :key="a.standard_number || a.std_code" class="announce-item">
      <span class="announce-code">{{ a.standard_number || a.std_code }}</span>
      <span class="announce-name">{{ a.standard_name || a.std_name }}</span>
    </div>
  </div>
</template>

<style scoped>
.announce-widget {
  height: 100%;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-xs);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.widget-header {
  font-weight: 600;
  color: var(--text-heading);
  font-size: 14px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.announce-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  gap: 10px;
  align-items: baseline;
  font-size: 12px;
}
.announce-item:last-child { border-bottom: none; }
.announce-code {
  flex-shrink: 0;
  color: var(--primary);
  font-weight: 500;
  font-family: var(--mono);
  font-size: 11px;
}
.announce-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-dim);
}

.empty {
  color: var(--text-dim);
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}

/* 骨架 */
.skeleton-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  gap: 10px;
}
.skeleton-line {
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.skeleton-code { height: 14px; width: 80px; flex-shrink: 0; }
.skeleton-name { height: 14px; flex: 1; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
