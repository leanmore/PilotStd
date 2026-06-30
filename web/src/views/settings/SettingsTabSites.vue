<script setup lang="ts">
import Tag from 'primevue/tag'

defineOptions({ name: 'SettingsTabSites' })

interface Site {
  name: string
  label: string
  url: string
  priority: number
  maxRequests: number
  dailyLimit: number
}

defineProps<{
  sites: Site[]
}>()
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">查询站点配置</div>
    <p class="text-dim mb-2">窗口上限 = 每轮冷却前最大请求数 | 日上限 = 当日累计超过后暂停使用（次日重置）</p>
    <div class="site-grid">
      <div v-for="s in sites" :key="s.name" class="site-card">
        <div class="site-head">
          <span class="site-priority">#{{ s.priority }}</span>
          <span class="site-name">{{ s.label }}</span>
          <Tag :value="s.name" severity="info" />
        </div>
        <div class="site-url text-mono text-dim">{{ s.url }}</div>
        <div class="site-limits">
          <div class="site-limit"><span class="lim-label">窗口上限</span><span class="lim-val">{{ s.maxRequests }} 次</span></div>
          <div class="site-limit"><span class="lim-label">日上限</span><span class="lim-val">{{ s.dailyLimit }} 次</span></div>
          <div class="site-limit"><span class="lim-label">冷却</span><span class="lim-val">10 分钟</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
