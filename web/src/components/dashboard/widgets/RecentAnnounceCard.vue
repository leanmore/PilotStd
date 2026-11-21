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
    const data = await getAnnounceResults(undefined, undefined, '/')
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
          <div class="header-title">{{ t('dashboard.card.recentAnnounce') }}</div>
          <span class="header-sub">{{ t('dashboard.recent_announce.subtitle') }}</span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="empty">{{ t('dashboard.common.loading') }}</div>
    <div v-else-if="!announcements.length" class="empty">{{ t('dashboard.recent_announce.empty') }}</div>

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
                  {{ item.announcement_title || item.announce_no || t('dashboard.recent_announce.untitled') }}
                </span>
                <span class="date">{{ item.publish_date || '' }}</span>
              </div>
              <div v-if="tab.items.length === 0" class="empty-state">{{ t('dashboard.recent_announce.tab_empty') }}</div>
            </div>
          </Transition>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
.root {
  height: 100%; box-sizing: border-box; padding: var(--space-14);
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; gap: var(--space-10);
}
.header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: var(--space-10); }
.header-icon {
  width: 34px; height: var(--icon-tile-md); border-radius: var(--radius-sm); background: var(--warning-bg);
  display: flex; align-items: center; justify-content: center; color: var(--warning); font-size: var(--font-size-16);
}
.header-title { font-size: var(--font-size-13); font-weight: var(--font-weight-bold); color: var(--text-heading); }
.header-sub { font-size: var(--font-size-10); color: var(--text-dim); }

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
  margin-left: var(--space-6);
}

/* 公告列表 */
.announce-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-top: var(--space-4);
}

.announce-item {
  padding: var(--space-6) 0;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}

.announce-item:hover {
  background: var(--selected);
}

.title-text {
  display: block;
  font-size: var(--font-size-12);
  font-weight: var(--font-weight-medium);
  color: var(--text-bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.date {
  font-size: var(--font-size-11);
  color: var(--text-dim);
  margin-top: var(--space-1);
}

.empty {
  color: var(--text-dim); font-size: var(--font-size-12); text-align: center;
  padding: var(--space-30) 0; flex: 1;
  display: flex; align-items: center; justify-content: center;
}

.empty-state {
  padding: var(--space-12) 0;
  text-align: center;
  color: var(--text-dim);
  font-size: var(--font-size-12);
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