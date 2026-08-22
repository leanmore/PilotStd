<script setup lang="ts">
defineOptions({ name: 'NotificationConfig' })
// NotificationConfig.vue v3 — 四渠道全参数通知配置（已移除页面内通知卡片）
import { ref, onMounted } from 'vue'
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

const EVENTS = [
  { key: 'archive_complete',          label: '归档完成' },
  { key: 'standard_status_changed',   label: '状态变更' },
  { key: 'standard_expired',          label: '标准废止' },
  { key: 'standard_first_registered', label: '首次登记' },
  { key: 'announcement_fetch_complete',  label: '公告抓取完成' },
  { key: 'auto_backup',                      label: '自动备份' },
  { key: 'announcement_check_complete',      label: '定时公告检查' },
  { key: 'auto_scan_failed',              label: '定时扫描异常' },
  { key: 'batch_download_complete',       label: '批量下载完成' },
  { key: 'validity_batch_report',         label: '时效性检查完成' },
  { key: 'validity_round_summary',        label: '周期总结汇报' },
  { key: 'validity_standard_failed',      label: '标准检查失败' },
  { key: 'validity_system_failed',        label: '系统执行异常' },
  { key: 'favorite_created',              label: '收藏成功' },
  { key: 'download_started',              label: '收藏下载开始' },
  { key: 'download_complete',             label: '收藏下载完成' },
  { key: 'download_failed',               label: '收藏下载失败' },
  { key: 'archive_abandoned',             label: '归档任务放弃' },
  { key: 'archive_failed',                label: '归档失败' },
  { key: 'normalize_complete',            label: '规范化完成' },
  { key: 'normalize_failed',              label: '规范化失败' },
  { key: 'scan_complete',                 label: '扫描完成' },
  { key: 'scan_empty',                    label: '扫描无新增' },
  { key: 'batch_query_summary',           label: '批量查询完成' },
  { key: 'query_failed',                  label: '查询失败' },
  { key: 'query_empty',                   label: '查询无结果' },
  { key: 'expire_standard_moved',         label: '废止标准移动' },
  { key: 'replacement_not_found',         label: '替代标准未找到' },
  { key: 'announcement_fetch_failed',     label: '公告抓取失败' },
  { key: 'announce_fetch_summary',        label: '公告逐站汇总' },
  { key: 'date_reminder',                 label: '日期到期提醒' },
  { key: 'task_execution_failed',         label: '定时任务异常' },
  { key: 'quota_exhausted',               label: '配额耗尽' },
  { key: 'trust_ip_update',               label: '可信IP更新' },
  { key: 'image_update_available',        label: '镜像更新可用' },
  { key: 'worker_error',                  label: '工作线程异常' },
]

const CHANNELS = [
  { key: 'wechat',   label: '企业微信', icon: 'pi pi-comments' },
  { key: 'telegram', label: 'Telegram',  icon: 'pi pi-send' },
  { key: 'feishu',   label: '飞书',      icon: 'pi pi-book' },
  { key: 'dingtalk', label: '钉钉',      icon: 'pi pi-bolt' },
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
        if (cfg.rules?.[ev.key]?.includes(ch)) channels.value[ch].events.push(ev.key)
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
    errMsg.value = err.response?.data?.error || '加载配置失败'
  } finally { loading.value = false }
}

async function saveConfig() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    const newRules: Record<string, string[]> = {}
    for (const ev of EVENTS) {
      newRules[ev.key] = []
      for (const ch of ['wechat', 'telegram', 'feishu', 'dingtalk']) {
        if (channels.value[ch].events.includes(ev.key)) newRules[ev.key].push(ch)
      }
    }
    await putNotificationConfig({
      enabled: enabled.value,
      channels: {
        wechat:   { enabled: channels.value.wechat.enabled,   webhook_url: channels.value.wechat.webhook_url,   corpid: channels.value.wechat.corpid, agentid: channels.value.wechat.agentid, corpsecret: channels.value.wechat.corpsecret, proxy_url: channels.value.wechat.proxy_url } as WechatChannelConfig,
        telegram: { enabled: channels.value.telegram.enabled, bot_token: channels.value.telegram.bot_token, chat_id: channels.value.telegram.chat_id } as TelegramChannelConfig,
        feishu:   { enabled: channels.value.feishu.enabled,   webhook_url: channels.value.feishu.webhook_url,   secret: channels.value.feishu.secret } as FeishuChannelConfig,
        dingtalk: { enabled: channels.value.dingtalk.enabled, webhook_url: channels.value.dingtalk.webhook_url, secret: channels.value.dingtalk.secret } as DingTalkChannelConfig,
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
    errMsg.value = err.response?.data?.error || '保存失败'
  } finally { saving.value = false }
}

defineExpose({ saveConfig })

async function testChannel(ch: string) {
  testResults.value[ch] = '测试中...'
  try {
    const c = channels.value[ch]
    const params: Record<string, string> = {}
    if (ch === 'telegram') { params.bot_token = c.bot_token; params.chat_id = c.chat_id }
    else if (ch === 'wechat') { params.webhook_url = c.webhook_url; params.corpid = c.corpid; params.agentid = c.agentid; params.corpsecret = c.corpsecret }
    else if (ch === 'feishu') { params.webhook_url = c.webhook_url; params.secret = c.secret }
    else if (ch === 'dingtalk') { params.webhook_url = c.webhook_url; params.secret = c.secret }
    const r = await testNotification(ch, params)
    testResults.value[ch] = r.ok ? '测试成功' : `失败: ${r.error || '未知'}`
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    testResults.value[ch] = `失败: ${err.response?.data?.error || (e instanceof Error ? e.message : '未知')}`
  }
  setTimeout(() => delete testResults.value[ch], 4000)
}

function chStatus(ch: string): string {
  const c = channels.value[ch]
  if (!c.enabled) return '未启用'
  if (ch === 'telegram') return c.bot_token && c.chat_id ? '已配置' : '待配置'
  if (ch === 'wechat') {
    if (c.corpid && c.agentid && c.corpsecret) return '应用消息'
    if (c.webhook_url) return '群机器人'
    return '待配置'
  }
  return c.webhook_url ? '已配置' : '待配置'
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
    <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <ToggleSwitch v-model="enabled" />
        <span style="font-size:13px;color:var(--text)">启用通知</span>
      </div>
    </div>

    <div class="channel-grid">
      <div v-for="ch in CHANNELS" :key="ch.key" class="collapsible-card">
        <div class="collapsible-header" @click="channelOpen[ch.key] = !channelOpen[ch.key]">
          <div style="display:flex;align-items:center;gap:8px">
            <i :class="ch.icon" style="font-size:16px;color:var(--primary)" />
            <span class="collapsible-title">{{ ch.label }}</span>
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
              <label>Bot Token <span class="required">*必填</span></label>
              <Password v-model="channels[ch.key].bot_token" class="w-full" placeholder="123456:ABC-DEF" size="small" toggleMask :feedback="false" />
            </div>
            <div class="field">
              <label>Chat ID <span class="required">*必填</span></label>
              <InputText v-model="channels[ch.key].chat_id" class="w-full" placeholder="-1001234567890" size="small" />
            </div>
            <div style="margin-top:8px">
              <Button label="测试" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <!-- 企业微信 -->
          <template v-else-if="ch.key === 'wechat'">
            <p style="font-size:11px;color:var(--text-dim);margin:0 0 10px">群机器人或企业应用消息，二选一</p>
            <div class="field">
              <label>Webhook URL <span class="optional">群机器人</span></label>
              <InputText v-model="channels[ch.key].webhook_url" class="w-full" placeholder="https://qyapi.weixin.qq.com/..." size="small" />
            </div>
            <div class="field-sep">或 企业应用消息</div>
            <div class="field">
              <label>企业 ID (corpid) <span class="optional">可选</span></label>
              <InputText v-model="channels[ch.key].corpid" class="w-full" placeholder="ww..." size="small" />
            </div>
            <div class="field">
              <label>应用 Agent ID <span class="optional">可选</span></label>
              <InputText v-model="channels[ch.key].agentid" class="w-full" placeholder="1000001" size="small" />
            </div>
            <div class="field">
              <label>应用 Secret <span class="optional">可选</span></label>
              <InputText v-model="channels[ch.key].corpsecret" class="w-full" placeholder="..." size="small" type="password" />
            </div>
            <div class="field">
              <label>代理地址 <span class="optional">可选</span></label>
              <InputText v-model="channels[ch.key].proxy_url" class="w-full" placeholder="http://proxy:8080" size="small" />
            </div>
            <div style="margin-top:8px">
              <Button label="测试" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <!-- 飞书 -->
          <template v-else-if="ch.key === 'feishu'">
            <div class="field">
              <label>Webhook URL <span class="required">*必填</span></label>
              <InputText v-model="channels[ch.key].webhook_url" class="w-full" placeholder="https://open.feishu.cn/..." size="small" />
            </div>
            <div class="field">
              <label>签名校验密钥 <span class="optional">选填</span></label>
              <Password v-model="channels[ch.key].secret" class="w-full" placeholder="加签密钥" size="small" toggleMask :feedback="false" />
            </div>
            <div style="margin-top:8px">
              <Button label="测试" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <!-- 钉钉 -->
          <template v-else-if="ch.key === 'dingtalk'">
            <div class="field">
              <label>Webhook URL <span class="required">*必填</span></label>
              <InputText v-model="channels[ch.key].webhook_url" class="w-full" placeholder="https://oapi.dingtalk.com/robot/..." size="small" />
            </div>
            <div class="field">
              <label>加签 Secret <span class="optional">选填</span></label>
              <Password v-model="channels[ch.key].secret" class="w-full" placeholder="SEC..." size="small" toggleMask :feedback="false" />
            </div>
            <div style="margin-top:8px">
              <Button label="测试" size="small" severity="secondary" @click="testChannel(ch.key)" />
            </div>
          </template>

          <div v-if="testResults[ch.key]" class="test-result">{{ testResults[ch.key] }}</div>

          <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
            <ToggleSwitch v-model="channels[ch.key].enabled" />
            <label style="font-size:12px;color:var(--text-dim)">启用此渠道</label>
          </div>

          <div class="events-row">
            <label class="events-label">事件订阅：</label>
            <div v-for="ev in EVENTS" :key="ev.key" class="checkbox-field">
              <Checkbox v-model="channels[ch.key].events" :value="ev.key" :input-id="`${ch.key}-${ev.key}`" />
              <label :for="`${ch.key}-${ev.key}`">{{ ev.label }}</label>
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
          <span class="collapsible-title">静音时段</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <Tag :severity="quietHoursEnabled ? 'success' : 'secondary'" :value="quietHoursEnabled ? '已启用' : '未启用'" />
        </div>
      </div>
      <div class="collapsible-content">
        <div class="config-row">
          <label>启用静音时段</label>
          <ToggleSwitch v-model="quietHoursEnabled" @change="saveQuietHours" />
          <span style="font-size:12px;color:var(--text-dim);margin-left:8px">
            静音时段内通知将暂存，结束后自动补发
          </span>
        </div>
        <div v-if="quietHoursEnabled" class="config-row" style="margin-top:8px">
          <label>开始时间</label>
          <AppCalendar v-model="quietHoursStart" timeOnly hourFormat="24" @update:model-value="saveQuietHours" />
          <label style="margin-left:16px">结束时间</label>
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
.field label { display: block; font-size: 12px; color: var(--text-dim); margin-bottom: 4px; }
.required { color: var(--danger); font-size: 10px; }
.optional { color: var(--text-dim); font-size: 10px; }
.field-sep { font-size: 11px; color: var(--text-dim); border-top: 1px dashed var(--border); padding-top: 8px; margin: 8px 0 6px; }
.w-full { width: 100%; }
.flex-1 { flex: 1; }
.test-result { font-size: 12px; margin-top: 6px; color: var(--text-dim); }
.events-row { margin-top: 10px; border-top: 1px solid var(--border-light); padding-top: 8px; }
.events-label { font-size: 12px; color: var(--text-dim); margin-bottom: 4px; display: block; }
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
