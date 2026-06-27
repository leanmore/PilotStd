<script setup lang="ts">
// NotificationConfig.vue v2 — 四渠道全参数通知配置
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import {
  getNotificationConfig, putNotificationConfig, testNotification,
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
  { key: 'check_batch_complete',      label: '批次完成' },
]

const CHANNELS = [
  { key: 'wechat',   label: '企业微信', icon: 'pi pi-comments' },
  { key: 'telegram', label: 'Telegram',  icon: 'pi pi-send' },
  { key: 'feishu',   label: '飞书',      icon: 'pi pi-book' },
  { key: 'dingtalk', label: '钉钉',      icon: 'pi pi-bolt' },
]

async function loadConfig() {
  loading.value = true; errMsg.value = ''
  try {
    const cfg = await getNotificationConfig()
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
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '加载配置失败'
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
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '保存失败'
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
  } catch (e: any) {
    testResults.value[ch] = `失败: ${e.response?.data?.error || e.message}`
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

onMounted(loadConfig)
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
      <Card v-for="ch in CHANNELS" :key="ch.key" class="channel-card">
        <template #title>
          <div class="ch-header">
            <div style="display:flex;align-items:center;gap:8px">
              <i :class="ch.icon" style="font-size:16px;color:var(--primary)" />
              <span>{{ ch.label }}</span>
            </div>
            <Tag :severity="chSeverity(ch.key)" :value="chStatus(ch.key)" />
          </div>
        </template>
        <template #content>
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
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.channel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.channel-card { border: 1px solid var(--border); border-radius: var(--radius); }
.ch-header { display: flex; align-items: center; justify-content: space-between; width: 100%; }
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
</style>
