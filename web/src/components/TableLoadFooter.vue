<!-- #40 增量加载底部状态指示器 -->
<script setup lang="ts">
defineProps<{
  totalCount: number
  displayCount: number
  isLoading: boolean
  isAllLoaded: boolean
  maxDisplay: number
}>()
</script>

<template>
  <div v-if="totalCount > 0" class="table-footer">
    <div v-if="isLoading" class="loading-indicator">
      <span class="spinner" />
      <span>加载更多标准...</span>
    </div>
    <div v-else-if="isAllLoaded && displayCount >= totalCount" class="all-loaded-indicator">
      已显示全部 {{ displayCount }} 条标准
    </div>
    <div v-else-if="isAllLoaded" class="limit-reached-indicator">
      仅显示前 {{ maxDisplay }} 条，共 {{ totalCount }} 条。请使用搜索缩小范围
    </div>
    <div v-else class="count-indicator">
      显示 {{ displayCount }} / {{ totalCount }} 条
    </div>
  </div>
</template>

<style scoped>
.table-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 0;
  color: var(--text-dim);
  font-size: 13px;
  gap: 12px;
}
.loading-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  animation: table-pulse 1.5s ease-in-out infinite;
}
.spinner {
  width: 24px; height: 24px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
.all-loaded-indicator {
  color: var(--text-dim);
  font-size: 13px;
}
.limit-reached-indicator {
  color: #ca8a04;
  font-size: 13px;
}
.count-indicator {
  color: var(--text-dim);
  font-size: 13px;
}
@keyframes table-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
