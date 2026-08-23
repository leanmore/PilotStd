<script setup lang="ts">
/**
 * SettingsTabSites — Q15: 站点限额/冷却编辑 + 权限控制 + 编辑/保存交互
 */
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import Tag from 'primevue/tag'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Message from 'primevue/message'
import http from '@/api/http'

defineOptions({ name: 'SettingsTabSites' })

const { t } = useI18n()
const toast = useToast()
const confirm = useConfirm()
const store = useAppStore()

interface SiteConfig {
  name: string
  label: string
  url: string
  priority: number
  maxRequests: number
  dailyLimit: number
  coolingSeconds: number
  requestInterval: number
  remainingQuota: number | null
  coolingRemaining: number | null
  lastHealthCheck: string | null
  healthStatus: string | null
}

const sites = ref<SiteConfig[]>([])
const loading = ref(false)
const saved = ref(false)
const errMsg = ref('')
const sections = ref({ sites: true })

// 每个站点的编辑状态 + 快照
const editStates = reactive<Record<string, {
  editing: boolean
  saving: boolean
  snapshot: SiteConfig | null
}>>({})

function snapshot(site: SiteConfig): SiteConfig {
  return JSON.parse(JSON.stringify(site))
}

function isAdmin() {
  return store.role === 'admin'
}

function validate(site: SiteConfig): string | null {
  if (site.maxRequests < 0) return t('sites.validation.max_requests_negative')
  if (site.dailyLimit < 0) return t('sites.validation.daily_limit_negative')
  if (site.coolingSeconds < 0) return t('sites.validation.cooling_negative')
  if (site.requestInterval < 0.1) return t('sites.validation.interval_min')
  return null
}

function isValid(site: SiteConfig): boolean {
  return validate(site) === null
}

function hasChanges(site: SiteConfig): boolean {
  const st = editStates[site.name]
  if (!st?.snapshot) return false
  return (
    site.maxRequests !== st.snapshot.maxRequests ||
    site.dailyLimit !== st.snapshot.dailyLimit ||
    site.coolingSeconds !== st.snapshot.coolingSeconds ||
    site.requestInterval !== st.snapshot.requestInterval
  )
}

function confirmDiscard(site: SiteConfig) {
  if (!hasChanges(site)) {
    cancelEdit(site)
    return
  }
  confirm.require({
    message: t('sites.discard_confirm'),
    header: t('common.confirm'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.confirm_discard'),
    rejectLabel: t('common.cancel'),
    accept: () => cancelEdit(site),
  })
}

function enterEdit(site: SiteConfig) {
  editStates[site.name] = {
    editing: true,
    saving: false,
    snapshot: snapshot(site),
  }
  // 解锁后自动聚焦第一个可编辑输入框
  nextTick(() => {
    const card = document.querySelector(`[data-site="${site.name}"]`)
    const input = card?.querySelector('input') as HTMLInputElement | null
    input?.focus()
  })
}

function cancelEdit(site: SiteConfig) {
  const st = editStates[site.name]
  if (st?.snapshot) {
    site.maxRequests = st.snapshot.maxRequests
    site.dailyLimit = st.snapshot.dailyLimit
    site.coolingSeconds = st.snapshot.coolingSeconds
    site.requestInterval = st.snapshot.requestInterval
  }
  delete editStates[site.name]
}

async function saveSite(site: SiteConfig) {
  const st = editStates[site.name]
  if (!st) return

  const err = validate(site)
  if (err) {
    // 同站点错误 toast 去重：先移除旧的再显示新的
    toast.removeGroup(site.name)
    toast.add({ group: site.name, severity: 'warn', summary: t('common.error'), detail: err, life: 3000 })
    return
  }

  st.saving = true
  try {
    await http.put(`/settings/sites/${site.name}`, {
      window_limit: site.maxRequests,
      daily_limit: site.dailyLimit,
      cooling_seconds: site.coolingSeconds,
      request_interval: site.requestInterval,
    })
    await loadSites()
    delete editStates[site.name]
    toast.add({ severity: 'success', summary: t('common.success'), detail: t('sites.saved', { label: site.label }), life: 3000 })
  } catch (e: any) {
    toast.removeGroup(site.name)
    toast.add({
      group: site.name,
      severity: 'error',
      summary: t('common.save_failed'),
      detail: e.response?.data?.detail || e.response?.data?.error || t('common.retry'),
      life: 5000,
    })
  } finally {
    st.saving = false
  }
}

function healthDotClass(s: SiteConfig): string {
  if (s.healthStatus === 'up') return 'health-up'
  if (s.healthStatus === 'down') return 'health-down'
  return 'health-none'
}

function healthText(s: SiteConfig): string {
  if (!s.lastHealthCheck) return t('sites.health_never')
  const ms = Date.now() - new Date(s.lastHealthCheck).getTime()
  const min = Math.max(0, Math.floor(ms / 60000))
  if (min < 60) return t('sites.health_checked_min', { min })
  return t('sites.health_checked_hour', { hour: Math.floor(min / 60) })
}

async function loadSites() {
  loading.value = true; errMsg.value = ''
  try {
    const r = await http.get('/settings/sites', { routeTag: '/settings' })
    if (!r || !r.data) return  // 请求被取消（响应拦截器静默返回 null），不显示错误
    sites.value = (r.data.sites || []).map((s: any) => ({
      ...s,
      coolingSeconds: s.cooling_seconds ?? 600,
      requestInterval: s.request_interval ?? 0.5,
      remainingQuota: s.remaining_quota ?? null,
      coolingRemaining: s.cooling_remaining ?? null,
      lastHealthCheck: s.last_health_check ?? null,
      healthStatus: s.health_status ?? null,
    }))
  } catch {
    toast.add({ severity: 'error', summary: t('sites.load_failed'), detail: t('common.check_network'), life: 5000 })
  } finally {
    loading.value = false
  }
}

onMounted(() => { loadSites() })
</script>

<template>
  <div class="collapsible-card mt-2">
    <div class="collapsible-header" @click="sections.sites = !sections.sites">
      <span class="collapsible-title">{{ t('sites.title') }}</span>
      <i :class="sections.sites ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="sections.sites" class="collapsible-content">
        <p class="text-dim mb-2">{{ t('sites.description') }}</p>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
        <Message v-if="saved" severity="success" :closable="false">{{ t('common.saved') }}</Message>
        <p v-if="!loading && sites.length === 0" class="text-dim text-center py-3">{{ t('sites.empty') }}</p>
        <div v-if="sites.length > 0" class="site-grid">
          <div
            v-for="s in sites"
            :key="s.name"
            :data-site="s.name"
            class="site-card"
            @keydown.escape="confirmDiscard(s)"
            @keydown.enter="editStates[s.name]?.editing && saveSite(s)"
          >
            <div class="site-head">
              <span class="site-priority">#{{ s.priority }}</span>
              <span class="site-name">{{ s.label }}</span>
              <Tag :value="s.name" severity="info" />
              <span class="health-dot" :class="healthDotClass(s)" :title="healthText(s)" />
              <Button
                v-if="isAdmin()"
                :icon="editStates[s.name]?.editing ? 'pi pi-lock-open' : 'pi pi-lock'"
                :severity="editStates[s.name]?.editing ? 'warn' : 'secondary'"
                :disabled="editStates[s.name]?.editing && !isValid(s)"
                :loading="editStates[s.name]?.saving"
                :title="editStates[s.name]?.editing
                  ? (isValid(s) ? t('sites.save_edit') : (validate(s) || t('sites.validation_failed')))
                  : t('sites.unlock_edit')"
                :aria-label="editStates[s.name]?.editing
                  ? (isValid(s) ? t('sites.save_edit') : (validate(s) || t('sites.validation_failed')))
                  : t('sites.unlock_edit')"
                rounded
                text
                size="small"
                class="lock-btn"
                @click="editStates[s.name]?.editing ? saveSite(s) : enterEdit(s)"
              />
              <!-- 编辑态：显式"放弃修改"按钮 -->
              <Button
                v-if="editStates[s.name]?.editing"
                icon="pi pi-undo"
                severity="secondary"
                :title="t('sites.discard_changes')"
                :aria-label="t('sites.discard_changes')"
                rounded
                text
                size="small"
                class="discard-btn"
                :disabled="editStates[s.name]?.saving"
                @click="confirmDiscard(s)"
              />
            </div>
            <div class="site-url text-mono text-dim">{{ s.url }}</div>
            <div class="site-fields">
              <div class="site-field">
                <label>{{ t('sites.max_requests') }}</label>
                <InputNumber
                  v-if="editStates[s.name]?.editing"
                  v-model="s.maxRequests"
                  :min="0" :step="1"
                  :inputClass="'edit-input'"
                />
                <span v-else class="field-value">{{ s.maxRequests }}</span>
              </div>
              <div class="site-field">
                <label>{{ t('sites.daily_limit') }}</label>
                <InputNumber
                  v-if="editStates[s.name]?.editing"
                  v-model="s.dailyLimit"
                  :min="0" :step="1"
                  :inputClass="'edit-input'"
                />
                <span v-else class="field-value">{{ s.dailyLimit }}</span>
              </div>
              <div class="site-field">
                <label>{{ t('sites.cooling_seconds') }}</label>
                <InputNumber
                  v-if="editStates[s.name]?.editing"
                  v-model="s.coolingSeconds"
                  :min="0" :step="1"
                  :inputClass="'edit-input'"
                />
                <span v-else class="field-value">{{ s.coolingSeconds }}</span>
              </div>
              <div class="site-field">
                <label>{{ t('sites.request_interval') }}</label>
                <InputNumber
                  v-if="editStates[s.name]?.editing"
                  v-model="s.requestInterval"
                  :min="0.1" :max="10" :step="0.1" :minFractionDigits="1"
                  :inputClass="'edit-input'"
                />
                <span v-else class="field-value">{{ s.requestInterval.toFixed(1) }}s</span>
              </div>
            </div>
            <div class="site-status">
              <span>{{ t('sites.today_remaining') }}：{{ s.remainingQuota ?? '--' }}</span>
              <span>{{ t('sites.cooling_remaining') }}：{{ s.coolingRemaining != null ? s.coolingRemaining + 's' : '--' }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
@import './shared.css';

.site-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.site-head .lock-btn {
  margin-left: auto;
}
.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  cursor: help;
}
.health-up { background: var(--success); }
.health-down { background: var(--danger); }
.health-none { background: var(--border-light, #ccc); }
.discard-btn {
  margin-left: 2px;
}
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
  color: var(--text-secondary);
}
.field-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-bright);
  padding: 4px 0;
}
.site-field :deep(.edit-input) {
  border-color: var(--primary-color) !important;
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
