<script setup lang="ts">
/**
 * RouteDebugPanel — Phase 3.2: 路由评分决策链调试面板
 *
 * 独立组件，不嵌入 SettingsTabSites.vue。
 * 展示完整评分链：适配器名 / 分数 / 原因标签。
 */
import { ref } from 'vue'
import http from '@/api/http'

defineOptions({ name: 'RouteDebugPanel' })

interface ScoreEntry {
  adapter: string
  score: number
  reasons: string[]
}

const query = ref('')
const runtimeJson = ref('')
const loading = ref(false)
const results = ref<ScoreEntry[]>([])
const error = ref('')

function reasonColor(reason: string): string {
  if (reason.startsWith('prefix_match')) return 'var(--primary)'
  if (reason.startsWith('industry_match')) return 'var(--success)'
  if (reason.startsWith('general:')) return 'var(--warning)'
  if (reason.includes('exhausted') || reason.includes('cooldown') || reason.includes('batch_limit'))
    return 'var(--danger)'
  if (reason.includes('not_found')) return 'var(--text-dim)'
  return 'var(--info)'
}

async function debug() {
  if (!query.value.trim()) return
  loading.value = true; error.value = ''
  try {
    const body: Record<string, unknown> = { query: query.value.trim() }
    if (runtimeJson.value.trim()) {
      try {
        body.simulate_runtime = JSON.parse(runtimeJson.value)
      } catch {
        error.value = 'JSON 格式错误，请检查 simulate_runtime'
        loading.value = false
        return
      }
    }
    const r = await http.post('/query/debug', body)
    results.value = r.data as ScoreEntry[]
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '请求失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="root">
    <div class="header">
      <div class="header-left">
        <i class="pi pi-search" style="color:var(--primary)" />
        <span class="title">路由调试</span>
      </div>
    </div>

    <div class="input-area">
      <div class="input-row">
        <input
          v-model="query"
          class="query-input"
          placeholder="输入查询词，如 NB/T 1234"
          @keyup.enter="debug"
        />
        <button class="debug-btn" :disabled="loading" @click="debug">
          {{ loading ? '分析中…' : '分析' }}
        </button>
      </div>
      <details class="simulate-toggle">
        <summary class="toggle-label">模拟运行时状态（可选 JSON）</summary>
        <textarea
          v-model="runtimeJson"
          class="json-input"
          rows="4"
          placeholder='{"csres": {"daily_used": 200, "cooldown_until": 0}}'
        />
      </details>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-if="results.length > 0" class="results">
      <div class="result-header">
        <span class="col-adapter">适配器</span>
        <span class="col-score">分数</span>
        <span class="col-reasons">评分原因</span>
      </div>
      <div
        v-for="r in results"
        :key="r.adapter"
        class="result-row"
        :class="{ dimmed: r.score === 0, highlight: r.score >= 80 }"
      >
        <span class="col-adapter">{{ r.adapter }}</span>
        <span class="col-score" :class="{ zero: r.score === 0 }">{{ r.score }}</span>
        <span class="col-reasons">
          <span
            v-for="reason in r.reasons"
            :key="reason"
            class="reason-tag"
            :style="{ background: reasonColor(reason) + '20', color: reasonColor(reason), borderColor: reasonColor(reason) + '40' }"
          >{{ reason }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.root {
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  max-width: 900px;
}
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.title { font-size: 14px; font-weight: 700; color: var(--text-heading); }
.input-area { margin-bottom: 12px; }
.input-row { display: flex; gap: 8px; }
.query-input {
  flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface-raised); color: var(--text); font-size: 13px;
}
.debug-btn {
  padding: 8px 16px; border: none; border-radius: var(--radius);
  background: var(--primary); color: #fff; cursor: pointer; font-size: 13px; font-weight: 600;
}
.debug-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.simulate-toggle { margin-top: 8px; }
.toggle-label { font-size: 11px; color: var(--text-dim); cursor: pointer; }
.json-input {
  width: 100%; margin-top: 4px; padding: 6px 8px; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface-raised); color: var(--text);
  font-family: monospace; font-size: 12px; resize: vertical; box-sizing: border-box;
}
.error-msg { padding: 8px; background: var(--danger-bg); color: var(--danger); border-radius: var(--radius); font-size: 12px; margin-bottom: 8px; }
.results { border: 1px solid var(--border-light); border-radius: var(--radius); overflow: hidden; }
.result-header {
  display: grid; grid-template-columns: 160px 60px 1fr; gap: 8px;
  padding: 8px 12px; background: var(--surface-raised); font-size: 11px; font-weight: 600; color: var(--text-dim);
}
.result-row {
  display: grid; grid-template-columns: 160px 60px 1fr; gap: 8px;
  padding: 8px 12px; border-top: 1px solid var(--border-light); font-size: 12px; align-items: center;
}
.result-row.dimmed { opacity: 0.35; }
.result-row.highlight { background: var(--primary-bg); }
.col-adapter { font-weight: 600; color: var(--text-heading); }
.col-score { font-weight: 700; }
.col-score.zero { color: var(--text-dim); }
.col-reasons { display: flex; flex-wrap: wrap; gap: 4px; }
.reason-tag {
  display: inline-block; padding: 1px 6px; border-radius: 10px; font-size: 10px;
  border: 1px solid; white-space: nowrap;
}
</style>
