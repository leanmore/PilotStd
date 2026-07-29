<script setup lang="ts">
defineOptions({ name: 'RecentAnnounceCard' })
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getAnnounceResults } from '@/api'
import type { AnnounceItem } from '@/types/api'

const { t } = useI18n()

const announcements = ref<AnnounceItem[]>([])
const loading = ref(true)

// API standard_type → 展示键映射
const API_TO_DISPLAY: Record<string, string> = {
  gb: 'national',
  hb: 'industry',
  db: 'local',
  other: 'other',
}

// Tab 排序优先级，未命中追加末尾
const SORT_ORDER = ['national', 'industry', 'local', 'other']

// 动态分组：基于 API 返回的 standard_type，每类最多 3 条
const groupedAnnouncements = computed(() => {
  const groups: Record<string, AnnounceItem[]> = {}
  for (const key of SORT_ORDER) {
    groups[key] = []
  }
  announcements.value.forEach(item => {
    const apiKey = item.standard_type || 'other'
    const displayKey = API_TO_DISPLAY[apiKey] || apiKey
    if (!groups[displayKey]) groups[displayKey] = []
    if (groups[displayKey].length < 3) groups[displayKey].push(item)
  })
  return groups
})

// Tab 列表：按排序规则排列，动态追加未知分类
const tabs = computed(() => {
  const allKeys = Object.keys(groupedAnnouncements.value)
  const sorted = SORT_ORDER.filter(k => allKeys.includes(k))
    .concat(allKeys.filter(k => !SORT_ORDER.includes(k)))
  return sorted.map(key => ({
    key,
    label: t(`announce.type.${key}`),
    count: groupedAnnouncements.value[key].length,
    items: groupedAnnouncements.value[key],
    disabled: groupedAnnouncements.value[key].length === 0,
  }))
})

// 默认选中第一个非空 Tab
const activeTab = ref<string>('')

onMounted(async () => {
  try {
    const data = await getAnnounceResults()
    announcements.value = data.results || []
  } catch { announcements.value = [] }
  finally {
    loading.value = false
    const firstNonEmpty = tabs.value.find(t => !t.disabled)
    activeTab.value = firstNonEmpty ? firstNonEmpty.key : (tabs.value[0]?.key || '')
  }
})
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <div class="header-icon"><i class="pi pi-bell" /></div>
        <div>
          <div class="header-title">最新公告</div>
          <span class="header-sub">实时推送</span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="empty">加载中...</div>
    <div v-else-if="!announcements.length" class="empty">暂无新公告</div>

    <Tabs v-else v-model:value="activeTab" class="tabs-root">
      <TabList>
        <Tab
          v-for="tab in tabs"
          :key="tab.key"
          :value="tab.key"
          :disabled="tab.disabled"
          :title="tab.disabled ? t('common.no_data') : undefined"
        >
          {{ tab.label }}
          <Badge :value="tab.count" class="tab-badge" />
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="tab in tabs" :key="tab.key" :value="tab.key">
          <Transition name="announce-fade" mode="out-in">
            <div v-if="activeTab === tab.key" :key="tab.key" class="announce-list">
              <div
                v-for="item in tab.items"
                :key="item.announce_no"
                class="announce-item"
              >
                <span class="title-text">
                  {{ item.announcement_title || item.announce_no || '无标题' }}
                </span>
                <span class="date">{{ item.publish_date || '' }}</span>
              </div>
              <div v-if="tab.items.length === 0" class="empty-state">暂无公告</div>
            </div>
          </Transition>
        </TabPanel>
      </TabPanels>
    </Tabs>
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

/* Tabs 容器 */
.tabs-root {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

/* Tab 数量徽标 */
.tab-badge {
  margin-left: 6px;
}

/* 公告列表 */
.announce-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-top: 4px;
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

/* Tab 切换过渡动画 */
.announce-fade-enter-active,
.announce-fade-leave-active {
  transition: opacity 0.2s ease;
}
.announce-fade-enter-from,
.announce-fade-leave-to {
  opacity: 0;
}
</style>