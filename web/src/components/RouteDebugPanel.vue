<script setup lang="ts">
/**
 * RouteDebugPanel — Phase 3.2: 路由评分决策链调试面板
 *
 * 独立组件，不嵌入 SettingsTabSites.vue。
 * 展示完整评分链：适配器名 / 分数 / 原因标签。
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'

defineOptions({ name: 'RouteDebugPanel' })

const { t } = useI18n()

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
        error.value = t('route_debug.err_json')
        loading.value = false
        return
      }
    }
    const r = await http.post('/query/debug', body)
    results.value = r.data as ScoreEntry[]
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || t('route_debug.err_request')
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
        <span class="title">{{ t('route_debug.title') }}</span>
      </div>
    </div>

    <div class="input-area">
      <div class="input-row">
        <input
          v-model="query"
          class="query-input"
          :placeholder="t('route_debug.input_ph')"
          @keyup.enter="debug"
        />
        <button class="debug-btn" :disabled="loading" @click="debug">
          {{ loading ? t('route_debug.analyzing') : t('route_debug.analyze') }}
        </button>
      </div>
      <details class="simulate-toggle">
        <summary class="toggle-label">{{ t('route_debug.simulate_label') }}</summary>
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
        <span class="col-adapter">{{ t('route_debug.col_adapter') }}</span>
        <span class="col-score">{{ t('route_debug.col_score') }}</span>
        <span class="col-reasons">{{ t('route_debug.col_reasons') }}</span>
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
  padding: var(--space-16);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  max-width: 900px;
}
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-12); }
.header-left { display: flex; align-items: center; gap: var(--space-8); }
.title { font-size: var(--font-size-14); font-weight: var(--font-weight-bold); color: var(--text-heading); }
.input-area { margin-bottom: var(--space-12); }
.input-row { display: flex; gap: var(--space-8); }
.query-input {
  flex: 1; padding: var(--space-8) var(--space-12); border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface-raised); color: var(--text); font-size: var(--font-size-13);
}
.debug-btn {
  padding: var(--space-8) var(--space-16); border: none; border-radius: var(--radius);
  /* TODO: [Design Debt] #fff 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: var(--primary-fill); color: var(--text-on-primary); cursor: pointer; font-size: var(--font-size-13); font-weight: var(--font-weight-semibold);
}
.debug-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.simulate-toggle { margin-top: var(--space-8); }
.toggle-label { font-size: var(--font-size-11); color: var(--text-dim); cursor: pointer; }
.json-input {
  width: 100%; margin-top: var(--space-4); padding: var(--space-6) var(--space-8); border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface-raised); color: var(--text);
  font-family: monospace; font-size: var(--font-size-12); resize: vertical; box-sizing: border-box;
}
.error-msg { padding: var(--space-8); background: var(--danger-bg); color: var(--danger); border-radius: var(--radius); font-size: var(--font-size-12); margin-bottom: var(--space-8); }
.results { border: 1px solid var(--border-light); border-radius: var(--radius); overflow: hidden; }
.result-header {
  display: grid; grid-template-columns: 160px 60px 1fr; gap: var(--space-8);
  padding: var(--space-8) var(--space-12); background: var(--surface-raised); font-size: var(--font-size-11); font-weight: var(--font-weight-semibold); color: var(--text-dim);
}
.result-row {
  display: grid; grid-template-columns: 160px 60px 1fr; gap: var(--space-8);
  padding: var(--space-8) var(--space-12); border-top: 1px solid var(--border-light); font-size: var(--font-size-12); align-items: center;
}
.result-row.dimmed { opacity: 0.35; }
.result-row.highlight { background: var(--primary-bg); }
.col-adapter { font-weight: var(--font-weight-semibold); color: var(--text-heading); }
.col-score { font-weight: var(--font-weight-bold); }
.col-score.zero { color: var(--text-dim); }
.col-reasons { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.reason-tag {
  /* TODO: [Design Debt] 10px 映射到旧令牌 --radius，待收敛到 ds-radius */
  display: inline-block; padding: var(--space-1) var(--space-6); border-radius: var(--radius); font-size: var(--font-size-10);
  border: 1px solid; white-space: nowrap;
}
</style>
