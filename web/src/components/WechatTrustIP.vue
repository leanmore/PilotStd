<script setup lang="ts">
defineOptions({ name: 'WechatTrustIP' })
// WechatTrustIP.vue — 企业微信可信 IP 自动更新配置
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/http'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import SelectButton from 'primevue/selectbutton'
import Dropdown from 'primevue/dropdown'
import Textarea from 'primevue/textarea'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'

interface WeworkIPConfig {
  enabled: boolean
  interval_hours: number
  ip_sources: string[]
  cookie_source: string
  cookiecloud_url: string
  cookiecloud_key: string
  cookiecloud_password: string
  cookie_status: string
  app_urls: string
  use_selenium: boolean
  headless: boolean
  engine: string
  update_mode: string
  notify_result: boolean
  last_ip: string
  last_check_at: string
}

interface WeworkIPStatus {
  current_ip: string
  last_ip: string
  ip_changed: boolean
  cookie_valid: boolean
  enabled: boolean
  last_check_at: string
}

const config = ref<WeworkIPConfig>({
  enabled: false, interval_hours: 6,
  ip_sources: ['https://myip.ipip.net', 'https://4.ipw.cn'],
  cookie_source: 'manual', cookiecloud_url: '', cookiecloud_key: '',
  cookiecloud_password: '', cookie_status: '', app_urls: '',
  update_mode: 'append', use_selenium: true, headless: true,
  engine: 'auto', notify_result: true, last_ip: '', last_check_at: '',
})

const status = ref<WeworkIPStatus>({
  current_ip: '', last_ip: '', ip_changed: false,
  cookie_valid: false, enabled: false, last_check_at: '',
})

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const saved = ref(false)
const errMsg = ref('')
const checkResult = ref('')
const cookieRaw = ref('')

const intervalOptions = computed(() => [
  { label: t('settings.wechat_ip.interval_hours', { n: 1 }), value: 1 },
  { label: t('settings.wechat_ip.interval_hours', { n: 6 }), value: 6 },
  { label: t('settings.wechat_ip.interval_hours', { n: 12 }), value: 12 },
  { label: t('settings.wechat_ip.interval_hours', { n: 24 }), value: 24 },
])

const cookieSourceOptions = computed(() => [
  { label: t('settings.wechat_ip.source_manual'), value: 'manual' },
  { label: 'CookieCloud', value: 'cookiecloud' },
])

const updateModeOptions = computed(() => [
  { label: t('settings.wechat_ip.mode_append'), value: 'append' },
  { label: t('settings.wechat_ip.mode_replace'), value: 'replace' },
])

const engineOptions = computed(() => [
  { label: t('settings.wechat_ip.engine_auto'), value: 'auto' },
  { label: t('settings.wechat_ip.engine_playwright'), value: 'playwright' },
])

async function loadConfig() {
  loading.value = true
  try {
    const r = await http.get('/wechat-ip/config', { routeTag: '/settings' })
    config.value = r.data
  } catch (e: unknown) {
    errMsg.value = t('settings.wechat_ip.load_failed')
  } finally { loading.value = false }
}

async function saveConfig() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    const body: Record<string, unknown> = { ...config.value }
    if (cookieRaw.value) body.cookie_raw = cookieRaw.value
    await http.put('/wechat-ip/config', body)
    saved.value = true; cookieRaw.value = ''
    setTimeout(() => saved.value = false, 2000)
    await loadStatus()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    errMsg.value = err.response?.data?.error || t('common.save_failed')
  } finally { saving.value = false }
}

async function loadStatus() {
  try {
    const r = await http.get('/wechat-ip/status', { routeTag: '/settings' })
    status.value = r.data
  } catch { /* ignore */ }
}

async function triggerCheck() {
  checking.value = true; checkResult.value = ''
  try {
    const r = await http.post('/wechat-ip/check')
    const d = r.data
    if (d.error) {
      checkResult.value = t('settings.wechat_ip.check_failed', { msg: d.error })
    } else if (d.updated) {
      checkResult.value = t('settings.wechat_ip.check_ok', { ip: d.detected_ip })
    } else if (d.changed) {
      checkResult.value = t('settings.wechat_ip.check_changed', { ip: d.detected_ip })
    } else {
      checkResult.value = t('settings.wechat_ip.check_same', { ip: d.detected_ip })
    }
    setTimeout(() => checkResult.value = '', 6000)
    await loadStatus()
  } catch (e: unknown) {
    checkResult.value = t('settings.wechat_ip.check_error', { msg: e instanceof Error ? e.message : String(e) })
  } finally { checking.value = false }
}

onMounted(() => { loadConfig(); loadStatus() })
</script>

<template>
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">{{ t('settings.saved') }}</Message>
    <Message v-if="checkResult" severity="info" :closable="false">{{ checkResult }}</Message>

    <!-- 总开关 + 当前状态 -->
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:10px">
        <ToggleSwitch v-model="config.enabled" />
        <span style="font-weight:600;font-size:14px">{{ t('settings.wechat_ip.title') }}</span>
        <Tag v-if="config.enabled" severity="success" :value="t('settings.wechat_ip.enabled')" />
        <Tag v-else severity="secondary" :value="t('settings.wechat_ip.disabled')" />
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <Button :label="t('settings.wechat_ip.check_now')" icon="pi pi-sync" size="small" :loading="checking" @click="triggerCheck" />
        <Button :label="t('settings.save_config')" icon="pi pi-check" size="small" severity="primary" :loading="saving" @click="saveConfig" />
      </div>
    </div>

    <!-- 状态栏 -->
    <div class="status-bar">
      <div class="status-item">
        <span class="status-label">{{ t('settings.wechat_ip.current_ip') }}</span>
        <!-- i18n-allow: 与后端返回的中文状态值（'未知'）比较，翻译即失效 -->
        <Tag :severity="status.current_ip !== '未知' ? 'success' : 'secondary'" :value="status.current_ip" />
      </div>
      <div class="status-item">
        <span class="status-label">{{ t('settings.wechat_ip.last_ip') }}</span>
        <span style="font-size:13px">{{ status.last_ip || t('settings.wechat_ip.none') }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">{{ t('settings.wechat_ip.ip_changed') }}</span>
        <Tag :severity="status.ip_changed ? 'warn' : 'info'" :value="status.ip_changed ? t('common.yes') : t('common.no')" />
      </div>
      <div class="status-item">
        <span class="status-label">{{ t('settings.wechat_ip.cookie_valid') }}</span>
        <Tag :severity="status.cookie_valid ? 'success' : 'danger'" :value="status.cookie_valid ? t('settings.wechat_ip.valid') : t('settings.wechat_ip.invalid')" />
      </div>
      <div class="status-item" v-if="status.last_check_at">
        <span class="status-label">{{ t('settings.wechat_ip.last_check') }}</span>
        <span style="font-size:12px;color:var(--text-dim)">{{ status.last_check_at }}</span>
      </div>
    </div>

    <!-- 配置区域 -->
    <Accordion>
      <AccordionTab :header="t('settings.wechat_ip.settings_title')">
        <div class="config-card-content">
          <div class="field">
            <label>{{ t('settings.wechat_ip.interval') }}</label>
            <Dropdown v-model="config.interval_hours" :options="intervalOptions" option-label="label" option-value="value" style="width:100%" />
          </div>
          <div class="field">
            <label>{{ t('settings.wechat_ip.app_urls') }}</label>
            <Textarea v-model="config.app_urls" rows="2" placeholder="https://work.weixin.qq.com/wework_admin/frame#/apps/modApiApp/00000000000" style="width:100%" />
            <small style="color:var(--text-dim)">{{ t('settings.wechat_ip.app_urls_hint') }}</small>
          </div>
          <div class="field">
            <label>{{ t('settings.wechat_ip.mode') }}</label>
            <SelectButton v-model="config.update_mode" :options="updateModeOptions" option-value="value" option-label="label" size="small" />
          </div>
          <div class="field" style="display:flex;align-items:center;gap:8px">
            <ToggleSwitch v-model="config.headless" />
            <label>{{ t('settings.wechat_ip.headless') }}</label>
          </div>
          <div class="field">
            <label>{{ t('settings.wechat_ip.engine') }}</label>
            <SelectButton v-model="config.engine" :options="engineOptions" option-value="value" option-label="label" size="small" />
          </div>
          <div class="field" style="display:flex;align-items:center;gap:8px">
            <ToggleSwitch v-model="config.notify_result" />
            <label>{{ t('settings.wechat_ip.notify') }}</label>
          </div>
        </div>
      </AccordionTab>

      <AccordionTab>
        <template #header>
          <div style="display:flex;align-items:center;justify-content:space-between;width:100%">
            <span>{{ t('settings.wechat_ip.cookie_title') }}</span>
            <!-- i18n-allow: 比较后端返回的中文 Cookie 状态值（'已配置'），翻译即失效（C-2，同第 173 行） -->
            <Tag :value="config.cookie_status" :severity="config.cookie_status.includes('已配置') ? 'success' : 'secondary'" />
          </div>
        </template>
        <div class="config-card-content">
          <div class="field">
            <label>{{ t('settings.wechat_ip.cookie_source') }}</label>
            <SelectButton v-model="config.cookie_source" :options="cookieSourceOptions" option-value="value" option-label="label" size="small" />
          </div>

          <!-- 手动导入 -->
          <template v-if="config.cookie_source === 'manual'">
            <div class="field">
              <label>{{ t('settings.wechat_ip.cookie_header') }}</label>
              <Textarea v-model="cookieRaw" rows="3" placeholder="key1=value1; key2=value2" style="width:100%" />
              <small style="color:var(--text-dim)">{{ t('settings.wechat_ip.cookie_hint') }}</small>
            </div>
          </template>

          <!-- CookieCloud -->
          <template v-if="config.cookie_source === 'cookiecloud'">
            <div class="field">
              <label>{{ t('settings.wechat_ip.cookiecloud_url') }}</label>
              <InputText v-model="config.cookiecloud_url" placeholder="http://127.0.0.1:8088" style="width:100%" />
            </div>
            <div class="field">
              <label>{{ t('settings.wechat_ip.cookiecloud_key') }}</label>
              <InputText v-model="config.cookiecloud_key" :placeholder="t('settings.wechat_ip.cookiecloud_key_placeholder')" style="width:100%" />
            </div>
            <div class="field">
              <label>{{ t('settings.wechat_ip.cookiecloud_password') }}</label>
              <InputText v-model="config.cookiecloud_password" :placeholder="t('settings.wechat_ip.cookiecloud_password_placeholder')" style="width:100%" type="password" />
            </div>
          </template>
        </div>
      </AccordionTab>
    </Accordion>
  </div>
</template>

<style scoped>
.status-bar { display: flex; gap: 20px; flex-wrap: wrap; padding: 12px 16px; background: var(--surface-raised); border-radius: var(--radius); margin-bottom: 16px; border: 1px solid var(--border); }
.status-item { display: flex; flex-direction: column; gap: 4px; }
.status-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.03em; }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 14px; }
.config-card { border: 1px solid var(--border); }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
</style>
