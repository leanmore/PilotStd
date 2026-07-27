<!-- #40 增量加载底部状态指示器（终版：含"加载全部"按钮） -->
<script setup lang="ts">
defineOptions({ name: 'TableLoadFooter' })

defineProps<{
  displayed: number
  total: number
  isLoading: boolean
  showLoadAllButton: boolean
}>()

defineEmits<{
  loadAll: []
}>()
</script>

<template>
  <div v-if="total > 0" class="table-load-footer">
    <div v-if="isLoading" class="footer-row">
      <span class="spinner" />
      <span>加载更多标准...</span>
    </div>
    <div v-else-if="displayed >= total" class="footer-row footer-complete">
      已显示全部 {{ total }} 条标准
    </div>
    <div v-else-if="showLoadAllButton" class="footer-row">
      <span class="partial-text">已显示前 {{ displayed }} / {{ total }} 条标准</span>
      <button class="load-all-btn" @click="$emit('loadAll')">
        加载剩余 {{ total - displayed }} 条
      </button>
    </div>
    <div v-else class="footer-row footer-hint">
      显示 {{ displayed }} / {{ total }} 条，滚动加载更多
    </div>
  </div>
</template>

<style scoped>
.table-load-footer {
  padding: 12px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--text-dim);
  border-top: 1px solid var(--border);
}
.footer-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.load-all-btn {
  padding: 4px 12px;
  border: 1px solid var(--primary);
  background: transparent;
  color: var(--primary);
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}
.load-all-btn:hover {
  background: var(--primary);
  color: #fff;
}
.partial-text {
  color: #ca8a04;
}
.spinner {
  width: 20px; height: 20px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
