<script setup lang="ts">
/**
 * SettingsTabSites — Q15: 站点限额/冷却可编辑 + 剩余配额显示
 */
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Tag from 'primevue/tag'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import http from '@/api/http'

defineOptions({ name: 'SettingsTabSites' })

const toast = useToast()

interface SiteConfig {
  name: string
  label: string
  url: string
  priority: number
  maxRequests: number
  dailyLimit: number
  coolingSeconds: number
  remainingQuota: number | null
  coolingRemaining: number | null
}

const sites = ref<SiteConfig[]>([])
const loading = ref(false)
const saved = ref(false)
const errMsg = ref('')
const sections = ref({ sites: true })

// 原始快照，用于变更检测与回滚
let original: SiteConfig[] = []

async function loadSites() {
  loading.value = true; errMsg.value = ''
  try {
    const r = await http.get('/settings/sites')
    sites.value = (r.data.sites || []).map((s: any) => ({
      ...s,
      coolingSeconds: s.cooling_seconds ?? 600,
      remainingQuota: s.remaining_quota ?? null,
      coolingRemaining: s.cooling_remaining ?? null,
    }))
    original = JSON.parse(JSON.stringify(sites.value))
  } catch {
    toast.add({ severity: 'error', summary: '站点列表加载失败', detail: '请检查网络后刷新重试', life: 5000 })
  } finally {
    loading.value = false
  }
}

let updateTimer: ReturnType<typeof setTimeout> | null = null

async function updateSite(site: SiteConfig) {
  if (updateTimer) clearTimeout(updateTimer)
  updateTimer = setTimeout(async () => {
    const orig = original.find(o => o.name === site.name)
    if (!orig) return
    if (
      site.maxRequests === orig.maxRequests &&
      site.dailyLimit === orig.dailyLimit &&
      site.coolingSeconds === orig.coolingSeconds
    ) return
    try {
      await http.put(`/settings/sites/${site.name}`, {
        window_limit: site.maxRequests,
        daily_limit: site.dailyLimit,
        cooling_seconds: site.coolingSeconds,
      })
      await loadSites()
      saved.value = true
      setTimeout(() => saved.value = false, 2000)
    } catch (e: any) {
      site.maxRequests = orig.maxRequests
      site.dailyLimit = orig.dailyLimit
      site.coolingSeconds = orig.coolingSeconds
      errMsg.value = '保存失败，已回滚'
    }
  }, 300)
}

onMounted(() => { loadSites() })
</script>

<template>
  <div class="collapsible-card mt-2">
    <div class="collapsible-header" @click="sections.sites = !sections.sites">
      <span class="collapsible-title">查询站点配置</span>
      <i :class="sections.sites ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="sections.sites" class="collapsible-content">
        <p class="text-dim mb-2">窗口上限 = 每轮冷却前最大请求数 | 日上限 = 当日累计超过后暂停使用（次日重置）</p>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
        <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>
        <p v-if="!loading && sites.length === 0" class="text-dim text-center py-3">暂无可用站点</p>
        <div v-if="sites.length > 0" class="site-grid">
          <div v-for="s in sites" :key="s.name" class="site-card">
            <div class="site-head">
              <span class="site-priority">#{{ s.priority }}</span>
              <span class="site-name">{{ s.label }}</span>
              <Tag :value="s.name" severity="info" />
            </div>
            <div class="site-url text-mono text-dim">{{ s.url }}</div>
            <!-- Q15: 可编辑限额 -->
            <div class="site-fields">
              <div class="site-field">
                <label>窗口查询限额</label>
                <InputNumber v-model="s.maxRequests" :min="1" :max="100000" @update:modelValue="updateSite(s)" />
              </div>
              <div class="site-field">
                <label>日限额</label>
                <InputNumber v-model="s.dailyLimit" :min="1" :max="100000" @update:modelValue="updateSite(s)" />
              </div>
              <div class="site-field">
                <label>冷却时间（秒）</label>
                <InputNumber v-model="s.coolingSeconds" :min="0" :max="3600" @update:modelValue="updateSite(s)" />
              </div>
            </div>
            <!-- Q15: 剩余配额显示 -->
            <div class="site-status">
              <span>今日剩余：{{ s.remainingQuota ?? '--' }}</span>
              <span>冷却剩余：{{ s.coolingRemaining != null ? s.coolingRemaining + 's' : '--' }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
@import './shared.css';

.site-fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light, #e5e7eb);
}
.site-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.site-field label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-dim);
}
.site-status {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--border-light, #e5e7eb);
  font-size: 12px;
  color: var(--text-dim);
}
</style>
