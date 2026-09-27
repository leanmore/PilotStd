<script setup lang="ts">
defineOptions({ name: 'NotificationConfig' })
// NotificationConfig.vue v3 — 四渠道全参数通知配置（已移除页面内通知卡片）
// 文案全部走 i18n（notification.config.* / notification.channel.*），不硬编码中文
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserPreferences } from '@/composables/useUserPreferences'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import AppCalendar from '@/components/AppCalendar.vue'
import {
  getNotificationConfig, putNotificationConfig, testNotification,
  getNotificationPolicies, putNotificationPolicy,
  type WechatChannelConfig, type TelegramChannelConfig,
  type FeishuChannelConfig, type DingTalkChannelConfig,
} from '@/api/notification'

const { t, te } = useI18n()

/** 事件类型 → i18n key（notification.event.<type>，与日志页共用同一套文案） */
function eventLabel(type: string): string {
  const key = `notification.event.${type}`
  return te(key) ? t(key) : type
}

interface ChannelFormState {
  enabled: boolean
  webhook_url: string
  bot_token: string
  chat_id: string
  secret: string
  corpid: string
  agentid: string
  corpsecret: string
  proxy_url: string
  events: string[]
}

const enabled = ref(false)
const channels = ref<Record<string, ChannelFormState>>({
  wechat:   { enabled: true, webhook_url: '', bot_token: '', chat_id: '', secret: '', corpid: '', agentid: '', corpsecret: '', proxy_url: '', events: [] },
  telegram: { enabled: false, webhook_url: '', bot_token: '', chat_id: '', secret: '', corpid: '', agentid: '', corpsecret: '', proxy_url: '', events: [] },
  feishu:   { enabled: false, webhook_url: '', bot_token: '', chat_id: '', secret: '', corpid: '', agentid: '', corpsecret: '', proxy_url: '', events: [] },
  dingtalk: { enabled: false, webhook_url: '', bot_token: '', chat_id: '', secret: '', corpid: '', agentid: '', corpsecret: '', proxy_url: '', events: [] },
})
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const errMsg = ref('')
const testResults = ref<Record<string, string>>({})

// 可订阅的事件类型（后端 event_type 原值）；文案 key = notification.event.<type>（与日志页共用）
const EVENTS = [
  'archive_complete',
  'standard_status_changed',
  'standard_first_registered',
  'announcement_fetch_complete',
  'auto_backup',
  'announcement_check_complete',
  'auto_scan_failed',
  'batch_download_complete',
  'validity_batch_report',
  'validity_round_summary',
  'validity_standard_failed',
  'validity_system_failed',
  'favorite_created',
  'download_started',
  'download_complete',
  'download_failed',
  'archive_abandoned',
  'archive_failed',
  'normalize_complete',
  'normalize_failed',
  'scan_complete',
  'scan_empty',
  'batch_query_summary',
  'query_failed',
  'query_empty',
  'expire_standard_moved',
  'replacement_not_found',
  'announcement_fetch_failed',
  'announce_fetch_summary',
  'date_reminder',
  'task_execution_failed',
  'quota_exhausted',
  'trust_ip_update',
  'image_update_available',
  'worker_error',
]

const CHANNELS = [
  { key: 'wechat',   labelKey: 'notification.channel.wechat',   icon: 'pi pi-comments' },
  { key: 'telegram', labelKey: 'notification.channel.telegram', icon: 'pi pi-send' },
  { key: 'feishu',   labelKey: 'notification.channel.feishu',   icon: 'pi pi-book' },
  { key: 'dingtalk', labelKey: 'notification.channel.dingtalk', icon: 'pi pi-bolt' },
]

const channelOpen = ref<Record<string, boolean>>({
  wechat: false,
  telegram: false,
  feishu: false,
  dingtalk: false,
})

async function loadConfig() {
  loading.value = true; errMsg.value = ''
  try {
    const cfg = await getNotificationConfig('/settings')
    enabled.value = cfg.enabled
    for (const ch of ['wechat', 'telegram', 'feishu', 'dingtalk'] as const) {
      const sc = cfg.channels?.[ch]
      if (!sc) continue
      channels.value[ch].enabled = sc.enabled ?? false
      if (ch === 'telegram') {
        const t = sc as TelegramChannelConfig
        channels.value[ch].bot_token = t.bot_token || ''
        channels.value[ch].chat_id = t.chat_id || ''
      } else if (ch === 'wechat') {
        const w = sc as WechatChannelConfig
        channels.value[ch].webhook_url = w.webhook_url || ''
        channels.value[ch].corpid = w.corpid || ''
        channels.value[ch].agentid = w.agentid || ''
        channels.value[ch].corpsecret = w.corpsecret || ''
        channels.value[ch].proxy_url = w.proxy_url || ''
      } else if (ch === 'feishu') {
        const f = sc as FeishuChannelConfig
        channels.value[ch].webhook_url = f.webhook_url || ''
        channels.value[ch].secret = f.secret || ''
      } else if (ch === 'dingtalk') {
        const d = sc as DingTalkChannelConfig
        channels.value[ch].webhook_url = d.webhook_url || ''
        channels.value[ch].secret = d.secret || ''
      }
      channels.value[ch].events = []
      for (const ev of EVENTS) {
        if (cfg.rules?.[ev]?.includes(ch)) channels.value[ch].events.push(ev)
      }
    }

    // 尝试从策略 API 加载事件订阅（优先于 config.json rules）
    try {
      const { policies } = await getNotificationPolicies()
      if (policies && policies.length > 0) {
        for (const p of policies) {
          if (channels.value[p.channel]) {
            channels.value[p.channel].events = [...p.events]
          }
        }
      }
    } catch { /* 策略 API 不可用时保持 config.json rules */ }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    errMsg.value = err.response?.data?.error || t('notification.config.load_failed')
  } finally { loading.value = false }
}

async function saveConfig() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    const newRules: Record<string, string[]> = {}
    for (const ev of EVENTS) {
      newRules[ev] = []
      for (const ch of ['wechat', 'telegram', 'feishu', 'dingtalk']) {
        if (channels.value[ch].events.includes(ev)) newRules[ev].push(ch)
      }
    }
    // P1 修复：敏感字段增量提交——掩码值（含 *）或空值不提交，保留 DB 原值
    const SENSITIVE_FIELDS = ['bot_token', 'webhook_url', 'secret', 'corpsecret']
    const cleanChannel = (chCfg: Record<string, any>): Record<string, any> => {
      const cleaned: Record<string, any> = {}
      for (const [k, v] of Object.entries(chCfg)) {
        if (SENSITIVE_FIELDS.includes(k)) {
          // 掩码回显值或空值跳过，避免覆盖真实凭据
          if (v && typeof v === 'string' && !v.includes('*') && v.trim() !== '') cleaned[k] = v
        } else {
          cleaned[k] = v
        }
      }
      return cleaned
    }
    await putNotificationConfig({
      enabled: enabled.value,
      channels: {
        wechat:   cleanChannel(channels.value.wechat),
        telegram: cleanChannel(channels.value.telegram),
        feishu:   cleanChannel(channels.value.feishu),
        dingtalk: cleanChannel(channels.value.dingtalk),
      },
      rules: newRules,
    })
    // 同时保存事件订阅到策略表
    for (const ch of ['wechat', 'telegram', 'feishu', 'dingtalk'] as const) {
      try {
        await putNotificationPolicy({ channel: ch, events: channels.value[ch].events })
      } catch { /* 策略 API 不可用时静默降级 */ }
    }
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    errMsg.value = err.response?.data?.error || t('common.save_failed')
  } finally { saving.value = false }
}

defineExpose({ saveConfig })

async function testChannel(ch: string) {
  testResults.value[ch] = t('notification.config.testing')
  try {
    const c = channels.value[ch]
    const params: Record<string, string> = {}
    if (ch === 'telegram') { params.bot_token = c.bot_token; params.chat_id = c.chat_id }
    else if (ch === 'wechat') { params.webhook_url = c.webhook_url; params.corpid = c.corpid; params.agentid = c.agentid; params.corpsecret = c.corpsecret }
    else if (ch === 'feishu') { params.webhook_url = c.webhook_url; params.secret = c.secret }
    else if (ch === 'dingtalk') { params.webhook_url = c.webhook_url; params.secret = c.secret }
    const r = await testNotification(ch, params)
    testResults.value[ch] = r.ok
      ? t('notification.config.test_ok')
      : t('notification.config.test_failed', { msg: r.error || t('notification.config.unknown') })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    const msg = err.response?.data?.error || (e instanceof Error ? e.message : t('notification.config.unknown'))
    testResults.value[ch] = t('notification.config.test_failed', { msg })
  }
  setTimeout(() => delete testResults.value[ch], 4000)
}

function chStatus(ch: string): string {
  const c = channels.value[ch]
  if (!c.enabled) return t('notification.config.status.disabled')
  if (ch === 'telegram') {
    return c.bot_token && c.chat_id
      ? t('notification.config.status.configured')
      : t('notification.config.status.pending')
  }
  if (ch === 'wechat') {
    if (c.corpid && c.agentid && c.corpsecret) return t('notification.config.status.app_message')
    if (c.webhook_url) return t('notification.config.status.group_robot')
    return t('notification.config.status.pending')
  }
  return c.webhook_url ? t('notification.config.status.configured') : t('notification.config.status.pending')
}

function chSeverity(ch: string): 'success' | 'secondary' | 'warn' {
  const c = channels.value[ch]
  if (!c.enabled) return 'secondary'
  if (ch === 'telegram') return c.bot_token && c.chat_id ? 'success' : 'secondary'
  if (ch === 'wechat') return (c.webhook_url || (c.corpid && c.agentid && c.corpsecret)) ? 'success' : 'secondary'
  return c.webhook_url ? 'success' : 'secondary'
}

// ── 静音时段配置（全局通知配置，独立区域） ──
const { quietHours: quietPrefs } = useUserPreferences()

const quietHoursEnabled = ref(quietPrefs.value.enabled)
const quietHoursStart = ref(new Date(2024, 0, 1, 22, 0))
const quietHoursEnd = ref(new Date(2024, 0, 1, 7, 0))

function saveQuietHours() {
  const hhmm = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  quietPrefs.value = { enabled: quietHoursEnabled.value, start: hhmm(quietHoursStart.value), end: hhmm(quietHoursEnd.value) }
}

function loadQuietHoursFromPrefs() {
  quietHoursEnabled.value = quietPrefs.value.enabled
  if (quietPrefs.value.start) {
    const [h, m] = quietPrefs.value.start.split(':').map(Number)
    quietHoursStart.value = new Date(2024, 0, 1, h, m)
  }
  if (quietPrefs.value.end) {
    const [h, m] = quietPrefs.value.end.split(':').map(Number)
    quietHoursEnd.value = new Date(2024, 0, 1, h, m)
  }
}

onMounted(() => {
  loadConfig()
  loadQuietHoursFromPrefs()
})
</script>

<template>
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">{{ t('notification.config.saved') }}</Message>

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <ToggleSwitch v-model="enabled" />
        <span style="font-size:13px;color:var(--text)">{{ t('notification.config.enable_all') }}</span>
      </div>
    </div>

    <div class="channel-grid">
      <div v-for="ch in CHANNELS" :key="ch.key" class="collapsible-card">
        <div class="collapsible-header" @click="channelOpen[ch.key] = !channelOpen[ch.key]">
          <div style="display:flex;align-items:center;gap:8px">
            <i :class="ch.icon" style="font-size:16px;color:var(--primary)" />
            <span class="collapsible-title">{{ t(ch.labelKey) }}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <Tag :severity="chSeverity(ch.key)" :value="chStatus(ch.key)" />
            <i :class="channelOpen[ch.key] ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
          </div>
        </div>
        <transition name="collapsible">
          <div v-show="channelOpen[ch.key]" class="collapsible-content">
          <!-- Telegram -->
          <template v-if="ch.key === 'telegram'">
            <div class="field">
              <label>Bot Token <span class="required">{{ t('notification.config.required') }}</span></label>
              <Password v-model="channels[ch.key].bot_token" class="w-full" placeholder="123456:ABC-DEF" size="small" toggleMask :feedback="false" />
            </div>
            <div class="field">
              <label>Chat ID <span class="required">{{ t('notification.config.required') }}</span></label>
              <InputText v-model="channels[ch.key].chat_id" class="w-full" placeholder="-1001234567890" size="small" />
            </div>
            <div style="margin-top:8px">
              <Button :label="t('notification.config.test')" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <!-- 企业微信 -->
          <template v-else-if="ch.key === 'wechat'">
            <p style="font-size:11px;color:var(--text-dim);margin:0 0 10px">{{ t('notification.config.wechat.hint') }}</p>
            <div class="field">
              <label>Webhook URL <span class="optional">{{ t('notification.config.wechat.group_robot_badge') }}</span></label>
              <InputText v-model="channels[ch.key].webhook_url" class="w-full" placeholder="https://qyapi.weixin.qq.com/..." size="small" />
            </div>
            <div class="field-sep">{{ t('notification.config.wechat.app_sep') }}</div>
            <div class="field">
              <label>{{ t('notification.config.wechat.corpid') }} <span class="optional">{{ t('notification.config.optional') }}</span></label>
              <InputText v-model="channels[ch.key].corpid" class="w-full" placeholder="ww..." size="small" />
            </div>
            <div class="field">
              <label>{{ t('notification.config.wechat.agentid') }} <span class="optional">{{ t('notification.config.optional') }}</span></label>
              <InputText v-model="channels[ch.key].agentid" class="w-full" placeholder="1000001" size="small" />
            </div>
            <div class="field">
              <label>{{ t('notification.config.wechat.corpsecret') }} <span class="optional">{{ t('notification.config.optional') }}</span></label>
              <InputText v-model="channels[ch.key].corpsecret" class="w-full" placeholder="..." size="small" type="password" />
            </div>
            <div class="field">
              <label>{{ t('notification.config.wechat.proxy_url') }} <span class="optional">{{ t('notification.config.optional') }}</span></label>
              <InputText v-model="channels[ch.key].proxy_url" class="w-full" placeholder="http://proxy:8080" size="small" />
            </div>
            <div style="margin-top:8px">
              <Button :label="t('notification.config.test')" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <!-- 飞书 -->
          <template v-else-if="ch.key === 'feishu'">
            <div class="field">
              <label>Webhook URL <span class="required">{{ t('notification.config.required') }}</span></label>
              <InputText v-model="channels[ch.key].webhook_url" class="w-full" placeholder="https://open.feishu.cn/..." size="small" />
            </div>
            <div class="field">
              <label>{{ t('notification.config.feishu.secret_label') }} <span class="optional">{{ t('notification.config.optional_short') }}</span></label>
              <Password v-model="channels[ch.key].secret" class="w-full" :placeholder="t('notification.config.feishu.secret_placeholder')" size="small" toggleMask :feedback="false" />
            </div>
            <div style="margin-top:8px">
              <Button :label="t('notification.config.test')" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <!-- 钉钉 -->
          <template v-else-if="ch.key === 'dingtalk'">
            <div class="field">
              <label>Webhook URL <span class="required">{{ t('notification.config.required') }}</span></label>
              <InputText v-model="channels[ch.key].webhook_url" class="w-full" placeholder="https://oapi.dingtalk.com/robot/..." size="small" />
            </div>
            <div class="field">
              <label>{{ t('notification.config.dingtalk.secret_label') }} <span class="optional">{{ t('notification.config.optional_short') }}</span></label>
              <Password v-model="channels[ch.key].secret" class="w-full" placeholder="SEC..." size="small" toggleMask :feedback="false" />
            </div>
            <div style="margin-top:8px">
              <Button :label="t('notification.config.test')" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <div v-if="testResults[ch.key]" class="test-result">{{ testResults[ch.key] }}</div>

          <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
            <ToggleSwitch v-model="channels[ch.key].enabled" />
            <label style="font-size:12px;color:var(--text-dim)">{{ t('notification.config.enable_channel') }}</label>
          </div>

          <div class="events-row">
            <label class="events-label">{{ t('notification.config.events_label') }}</label>
            <div v-for="ev in EVENTS" :key="ev" class="checkbox-field">
              <Checkbox v-model="channels[ch.key].events" :value="ev" :input-id="`${ch.key}-${ev}`" />
              <label :for="`${ch.key}-${ev}`">{{ eventLabel(ev) }}</label>
            </div>
          </div>
          </div>
        </transition>
      </div>
    </div>

    <!-- 静音时段（全局通知配置） -->
    <div class="collapsible-card" style="margin-top:16px">
      <div class="collapsible-header" style="cursor:default">
        <div style="display:flex;align-items:center;gap:8px">
          <i class="pi pi-moon" style="font-size:16px;color:var(--primary)" />
          <span class="collapsible-title">{{ t('notification.config.quiet_hours.title') }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <Tag :severity="quietHoursEnabled ? 'success' : 'secondary'" :value="quietHoursEnabled ? t('notification.config.quiet_hours.enabled') : t('notification.config.quiet_hours.disabled')" />
        </div>
      </div>
      <div class="collapsible-content">
        <div class="config-row">
          <label>{{ t('notification.config.quiet_hours.enable') }}</label>
          <ToggleSwitch v-model="quietHoursEnabled" @change="saveQuietHours" />
          <span style="font-size:12px;color:var(--text-dim);margin-left:8px">
            {{ t('notification.config.quiet_hours.hint') }}
          </span>
        </div>
        <div v-if="quietHoursEnabled" class="config-row" style="margin-top:8px">
          <label>{{ t('notification.config.quiet_hours.start') }}</label>
          <AppCalendar v-model="quietHoursStart" timeOnly hourFormat="24" @update:model-value="saveQuietHours" />
          <label style="margin-left:16px">{{ t('notification.config.quiet_hours.end') }}</label>
          <AppCalendar v-model="quietHoursEnd" timeOnly hourFormat="24" @update:model-value="saveQuietHours" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.channel-grid { display: flex; flex-direction: column; gap: 12px; }

.collapsible-card {
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs); overflow: hidden; transition: all var(--transition);
}
.collapsible-card:hover { box-shadow: var(--shadow-sm); }
.collapsible-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; cursor: pointer; user-select: none;
  background: linear-gradient(180deg, var(--surface), var(--surface-raised));
  border-bottom: 1px solid transparent; transition: all var(--transition);
}
.collapsible-header:hover { background: var(--selected); border-bottom-color: var(--border); }

.collapsible-title { font-size: 14px; font-weight: 700; color: var(--text-heading); }

.collapsible-icon {
  font-size: 13px; color: var(--text-dim); transition: transform var(--transition);
  padding: 2px; border-radius: var(--radius-sm);
}
.collapsible-header:hover .collapsible-icon { color: var(--primary); background: var(--primary-bg); }
.collapsible-content { padding: 16px 18px; }
.collapsible-enter-active,
.collapsible-leave-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.collapsible-enter-from,
.collapsible-leave-to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; }

.field { margin-bottom: 8px; }
.field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.required { color: var(--danger); font-size: 10px; }
.optional { color: var(--text-dim); font-size: 10px; }
.field-sep { font-size: 11px; color: var(--text-dim); border-top: 1px dashed var(--border); padding-top: 8px; margin: 8px 0 6px; }
.w-full { width: 100%; }
.flex-1 { flex: 1; }
.test-result { font-size: 12px; margin-top: 6px; color: var(--text-dim); }
.events-row { margin-top: 10px; border-top: 1px solid var(--border-light); padding-top: 8px; }
.events-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; display: block; }
.checkbox-field { display: inline-flex; align-items: center; gap: 4px; margin-right: 12px; margin-top: 4px; }
.checkbox-field label { font-size: 12px; color: var(--text); }
.events-check-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 4px 8px; margin-top: 6px;
}
.config-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.config-row label { font-size: 13px; color: var(--text); }
</style>
