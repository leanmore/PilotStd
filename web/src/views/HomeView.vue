<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getStats, getAnnounceResults } from '@/api'

const { t } = useI18n()
const router = useRouter()
const stats = ref<any>({})
const announces = ref<any[]>([])
const statsErr = ref(false)
const loading = ref(true)

onMounted(async () => {
  try { stats.value = await getStats() } catch { statsErr.value = true }
  try { announces.value = (await getAnnounceResults()).results?.slice(0, 5) || [] } catch {}
  loading.value = false
})

const statCards = [
  { key: 'current', label: t('home.current'), icon: 'pi pi-verified', gradient: 'linear-gradient(135deg, #10b981, #34d399)' },
  { key: 'expired', label: t('home.expired'), icon: 'pi pi-times-circle', gradient: 'linear-gradient(135deg, #ef4444, #f87171)' },
  { key: 'pending', label: t('home.pending'), icon: 'pi pi-hourglass', gradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)' },
  { key: 'upcoming', label: t('home.upcoming'), icon: 'pi pi-calendar-plus', gradient: 'linear-gradient(135deg, #3b82f6, #60a5fa)' },
]

const quickActions = [
  { label: '任务流水线', desc: '扫描→查询→下载→整理→归档 全流程', icon: 'pi pi-play', to: '/task', color: '#6366f1' },
  { label: '文件管理', desc: '浏览和管理已下载的文件', icon: 'pi pi-folder', to: '/organize', color: '#f59e0b' },
  { label: '待确认清单', desc: '查看需人工确认的标准', icon: 'pi pi-hourglass', to: '/pending', color: '#3b82f6' },
  { label: '公告检查', desc: '检查标准信息的更新公告', icon: 'pi pi-megaphone', to: '/announce', color: '#10b981' },
]
</script>

<template>
  <div class="page-header">
    <div>
      <h1>PilotStd</h1>
      <p class="hint">标准管理控制台</p>
    </div>
  </div>

  <!-- 统计卡片 —— 加载时显示骨架 -->
  <div class="stats-row">
    <template v-if="loading">
      <div v-for="n in 4" :key="'sk'+n" class="stat-card skeleton">
        <div class="stat-icon-box skeleton-box" />
        <div class="stat-info">
          <div class="skeleton-line skeleton-num" />
          <div class="skeleton-line skeleton-label" />
        </div>
      </div>
    </template>
    <template v-else>
      <div v-for="card in statCards" :key="card.key" class="stat-card">
        <div class="stat-icon-box" :style="{ background: card.gradient }">
          <i :class="card.icon" />
        </div>
        <div class="stat-info">
          <div class="stat-num" :class="{ 'stat-err': statsErr }">{{ statsErr ? '—' : (stats[card.key] ?? '—') }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
      </div>
    </template>
  </div>
  <p v-if="statsErr" class="hint-err">统计加载失败，请检查后端服务</p>

  <div class="home-grid">
    <!-- 快捷操作 -->
    <div class="card">
      <div class="card-header">快捷操作</div>
      <div class="quick-actions">
        <button
          v-for="act in quickActions"
          :key="act.to"
          @click="router.push(act.to)"
          class="action-btn"
        >
          <div class="action-icon" :style="{ background: act.color }">
            <i :class="act.icon" />
          </div>
          <div class="action-text">
            <span class="action-label">{{ act.label }}</span>
            <span class="action-desc">{{ act.desc }}</span>
          </div>
          <i class="pi pi-chevron-right action-arrow" />
        </button>
      </div>
    </div>

    <!-- 最近公告 -->
    <div class="card">
      <div class="card-header">最近公告</div>
      <p v-if="announces.length === 0" class="text-dim" style="text-align:center;padding:20px 0">暂无数据</p>
      <div v-for="a in announces" :key="a.standard_number || a.std_code" class="announce-item">
        <span class="announce-code text-mono">{{ a.standard_number || a.std_code }}</span>
        <span class="announce-name text-dim">{{ a.standard_name || a.std_name }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

/* 统计卡片 — 参考 MoviePilot Dashboard 设计 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition), transform var(--transition);
}
.stat-card:hover {
  box-shadow: var(--shadow);
  transform: translateY(-1px);
}

.stat-icon-box {
  width: 48px;
  height: 48px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-info { flex: 1; min-width: 0; }
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-heading);
  font-family: var(--mono);
  line-height: 1.2;
  letter-spacing: -0.02em;
}
.stat-label {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 2px;
  font-weight: 500;
}
.stat-err { color: var(--danger, #e74c3c); }
.hint-err { color: var(--danger, #e74c3c); font-size: 12px; margin: -12px 0 16px; }

/* 首页网格 */
.home-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 768px) {
  .home-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}

/* 快捷操作 */
.quick-actions { display: flex; flex-direction: column; gap: 6px; }

.action-btn {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 14px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;
  color: var(--text);
  transition: all var(--transition);
}
.action-btn:hover {
  background: var(--selected);
  border-color: var(--primary-border);
  box-shadow: var(--shadow-sm);
}
.action-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 17px;
}
.action-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.action-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-heading);
}
.action-desc {
  font-size: 12px;
  color: var(--text-dim);
}
.action-arrow {
  color: var(--text-dim);
  font-size: 13px;
  flex-shrink: 0;
}

/* 公告列表 */
.announce-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-size: 13px;
}
.announce-item:last-child { border-bottom: none; }
.announce-code {
  flex-shrink: 0;
  color: var(--primary);
  font-weight: 500;
}
.announce-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 响应式 */
@media (max-width: 767px) {
  .stat-card { padding: 14px; gap: 12px; }
  .stat-icon-box { width: 40px; height: 40px; font-size: 17px; }
  .stat-num { font-size: 22px; }
  .action-btn { padding: 12px; }
  .action-icon { width: 36px; height: 36px; font-size: 15px; }
}

/* 骨架加载 */
.skeleton .skeleton-box { background: var(--border-light); }
.skeleton-line {
  background: linear-gradient(90deg, var(--border-light) 25%, var(--border) 50%, var(--border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.skeleton-num { height: 28px; width: 60%; margin-bottom: 6px; }
.skeleton-label { height: 14px; width: 40%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
