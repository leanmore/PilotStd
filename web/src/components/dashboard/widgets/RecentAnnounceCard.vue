<script setup lang="ts">
defineOptions({ name: 'RecentAnnounceCard' })
import { ref, onMounted, computed } from 'vue'
import { getAnnounceResults } from '@/api'
import type { AnnounceItem } from '@/types/api'

const announcements = ref<AnnounceItem[]>([])
const loading = ref(true)

// ✅ #47: 类型标签（使用 sourceMapping 已有关键词）
const typeLabels: Record<string, string> = {
  gb: '国家公告',
  hb: '行业公告',
  db: '地方公告',
  other: '其他公告',
}

// ✅ #47: 按 standard_type 分组，每类取最新 3 条
const groupedAnnouncements = computed(() => {
  const groups: Record<string, AnnounceItem[]> = { gb: [], hb: [], db: [], other: [] }
  announcements.value.forEach(item => {
    const key = item.standard_type || 'other'
    if (groups[key]) groups[key].push(item)
  })
  return {
    gb: groups.gb.slice(0, 3),
    hb: groups.hb.slice(0, 3),
    db: groups.db.slice(0, 3),
    other: groups.other.slice(0, 3),
  }
})

onMounted(async () => {
  try {
    const data = await getAnnounceResults()
    announcements.value = data.results || []
  } catch { announcements.value = [] }
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
    <div v-else-if="!announcements.length" class="empty">暂无新公告</div>

    <!-- ✅ #47: 三栏分组展示，按 standard_type 分类 -->
    <div v-else class="three-columns">
      <div
        v-for="(items, type) in groupedAnnouncements"
        :key="type"
        class="column"
      >
        <div class="column-header">
          <span class="type-label">{{ typeLabels[type as string] }}</span>
          <span class="count">{{ items.length }}</span>
        </div>
        <div class="announce-list">
          <div
            v-for="item in items"
            :key="item.announce_no"
            class="announce-item"
          >
            <span class="title-text">
              {{ item.announcement_title || item.announce_no || '无标题' }}
            </span>
            <span class="date">{{ item.publish_date || '' }}</span>
          </div>
          <div v-if="items.length === 0" class="empty-state">暂无公告</div>
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

/* ✅ #47: 三栏 grid 布局 */
.three-columns {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 12px;
  overflow: hidden;
}

/* 移动端降级为单栏 */
@media (max-width: 768px) {
  .three-columns {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

.column {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 6px;
  margin-bottom: 6px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.type-label {
  font-weight: 600;
  font-size: 12px;
  color: var(--text-heading);
}

.count {
  font-size: 11px;
  color: var(--text-dim);
  background: var(--surface-raised);
  padding: 1px 6px;
  border-radius: 10px;
}

.announce-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.announce-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}

.announce-item:hover {
  background: var(--selected);
}

.title-text {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.date {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 1px;
}

.empty {
  color: var(--text-dim); font-size: 12px; text-align: center;
  padding: 30px 0; flex: 1;
  display: flex; align-items: center; justify-content: center;
}

.empty-state {
  padding: 12px 0;
  text-align: center;
  color: var(--text-dim);
  font-size: 12px;
}
</style>
