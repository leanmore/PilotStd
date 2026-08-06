<script setup lang="ts">
defineOptions({ name: 'WechatTrustIP' })
// WechatTrustIP.vue — 企业微信可信 IP 自动更新配置
import { ref, onMounted } from 'vue'
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

const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const saved = ref(false)
const errMsg = ref('')
const checkResult = ref('')
const cookieRaw = ref('')

const intervalOptions = [
  { label: '1 小时', value: 1 }, { label: '6 小时', value: 6 },
  { label: '12 小时', value: 12 }, { label: '24 小时', value: 24 },
]

const cookieSourceOptions = [
  { label: '手动导入', value: 'manual' },
  { label: 'CookieCloud', value: 'cookiecloud' },
]

const updateModeOptions = [
  { label: '追加（保留旧IP）', value: 'append' },
  { label: '覆盖（仅新IP）', value: 'replace' },
]

const engineOptions = [
  { label: 'CloakBrowser（推荐）', value: 'auto' },
  { label: 'Playwright 备选', value: 'playwright' },
]

async function loadConfig() {
  loading.value = true
  try {
    const r = await http.get('/wechat-ip/config')
    config.value = r.data
  } catch (e: unknown) {
    errMsg.value = '加载配置失败'
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
    errMsg.value = err.response?.data?.error || '保存失败'
  } finally { saving.value = false }
}

async function loadStatus() {
  try {
    const r = await http.get('/wechat-ip/status')
    status.value = r.data
  } catch { /* ignore */ }
}

async function triggerCheck() {
  checking.value = true; checkResult.value = ''
  try {
    const r = await http.post('/wechat-ip/check')
    const d = r.data
    if (d.error) {
      checkResult.value = `失败: ${d.error}`
    } else if (d.updated) {
      checkResult.value = `成功: IP 已更新为 ${d.detected_ip}`
    } else if (d.changed) {
      checkResult.value = `检测到 IP 变化: ${d.detected_ip}（未成功更新）`
    } else {
      checkResult.value = `IP 未变化: ${d.detected_ip}`
    }
    setTimeout(() => checkResult.value = '', 6000)
    await loadStatus()
  } catch (e: unknown) {
    checkResult.value = `请求失败: ${e instanceof Error ? e.message : String(e)}`
  } finally { checking.value = false }
}

onMounted(() => { loadConfig(); loadStatus() })
</script>

<template>
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>
    <Message v-if="checkResult" severity="info" :closable="false">{{ checkResult }}</Message>

    <!-- 总开关 + 当前状态 -->
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:10px">
        <ToggleSwitch v-model="config.enabled" />
        <span style="font-weight:600;font-size:14px">可信 IP 自动更新</span>
        <Tag v-if="config.enabled" severity="success" value="已启用" />
        <Tag v-else severity="secondary" value="已停用" />
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <Button label="检测并更新" icon="pi pi-sync" size="small" :loading="checking" @click="triggerCheck" />
        <Button label="保存配置" icon="pi pi-check" size="small" severity="primary" :loading="saving" @click="saveConfig" />
      </div>
    </div>

    <!-- 状态栏 -->
    <div class="status-bar">
      <div class="status-item">
        <span class="status-label">当前公网 IP</span>
        <Tag :severity="status.current_ip !== '未知' ? 'success' : 'secondary'" :value="status.current_ip" />
      </div>
      <div class="status-item">
        <span class="status-label">上次记录 IP</span>
        <span style="font-size:13px">{{ status.last_ip || '无' }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">IP 已变化</span>
        <Tag :severity="status.ip_changed ? 'warn' : 'info'" :value="status.ip_changed ? '是' : '否'" />
      </div>
      <div class="status-item">
        <span class="status-label">Cookie 有效</span>
        <Tag :severity="status.cookie_valid ? 'success' : 'danger'" :value="status.cookie_valid ? '有效' : '无效'" />
      </div>
      <div class="status-item" v-if="status.last_check_at">
        <span class="status-label">上次检测</span>
        <span style="font-size:12px;color:var(--text-dim)">{{ status.last_check_at }}</span>
      </div>
    </div>

    <!-- 配置区域 -->
    <Accordion>
      <AccordionTab header="检测设置">
        <div class="config-card-content">
          <div class="field">
            <label>检测间隔</label>
            <Dropdown v-model="config.interval_hours" :options="intervalOptions" option-label="label" option-value="value" style="width:100%" />
          </div>
          <div class="field">
            <label>应用管理地址（多个用逗号分隔）</label>
            <Textarea v-model="config.app_urls" rows="2" placeholder="https://work.weixin.qq.com/wework_admin/frame#/apps/modApiApp/00000000000" style="width:100%" />
            <small style="color:var(--text-dim)">从浏览器地址栏复制应用管理页面的完整 URL</small>
          </div>
          <div class="field">
            <label>IP 更新模式</label>
            <SelectButton v-model="config.update_mode" :options="updateModeOptions" option-value="value" option-label="label" size="small" />
          </div>
          <div class="field" style="display:flex;align-items:center;gap:8px">
            <ToggleSwitch v-model="config.headless" />
            <label>Headless 模式（无界面运行）</label>
          </div>
          <div class="field">
            <label>浏览器引擎</label>
            <SelectButton v-model="config.engine" :options="engineOptions" option-value="value" option-label="label" size="small" />
          </div>
          <div class="field" style="display:flex;align-items:center;gap:8px">
            <ToggleSwitch v-model="config.notify_result" />
            <label>更新结果通知</label>
          </div>
        </div>
      </AccordionTab>

      <AccordionTab>
        <template #header>
          <div style="display:flex;align-items:center;justify-content:space-between;width:100%">
            <span>Cookie 管理</span>
            <Tag :value="config.cookie_status" :severity="config.cookie_status.includes('已配置') ? 'success' : 'secondary'" />
          </div>
        </template>
        <div class="config-card-content">
          <div class="field">
            <label>Cookie 来源</label>
            <SelectButton v-model="config.cookie_source" :options="cookieSourceOptions" option-value="value" option-label="label" size="small" />
          </div>

          <!-- 手动导入 -->
          <template v-if="config.cookie_source === 'manual'">
            <div class="field">
              <label>Cookie (HeaderString 格式)</label>
              <Textarea v-model="cookieRaw" rows="3" placeholder="key1=value1; key2=value2" style="width:100%" />
              <small style="color:var(--text-dim)">从浏览器 DevTools → Network → 请求头 → Cookie 复制</small>
            </div>
          </template>

          <!-- CookieCloud -->
          <template v-if="config.cookie_source === 'cookiecloud'">
            <div class="field">
              <label>CookieCloud 服务地址</label>
              <InputText v-model="config.cookiecloud_url" placeholder="http://127.0.0.1:8088" style="width:100%" />
            </div>
            <div class="field">
              <label>用户密钥</label>
              <InputText v-model="config.cookiecloud_key" placeholder="从 CookieCloud 插件获取" style="width:100%" />
            </div>
            <div class="field">
              <label>端到端加密密码（可选）</label>
              <InputText v-model="config.cookiecloud_password" placeholder="如未设置则留空" style="width:100%" type="password" />
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
.field label { display: block; font-size: 12px; color: var(--text-dim); margin-bottom: 4px; font-weight: 500; }
</style>
