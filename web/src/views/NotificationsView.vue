<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import {
  getNotificationConfig,
  putNotificationConfig,
  testNotification,
  type WechatChannelConfig,
  type TelegramChannelConfig,
  type FeishuChannelConfig,
} from '@/api/notification'

// 渠道状态：本地编辑用的统一结构（所有字段可选，方便表单绑定）
interface ChannelFormState {
  enabled: boolean
  webhook_url: string
  bot_token: string
  chat_id: string
  events: string[]
}

const enabled = ref(false)
const channels = ref<Record<string, ChannelFormState>>({
  wechat: { enabled: true, webhook_url: '', bot_token: '', chat_id: '', events: [] },
  telegram: { enabled: false, webhook_url: '', bot_token: '', chat_id: '', events: [] },
  feishu: { enabled: false, webhook_url: '', bot_token: '', chat_id: '', events: [] },
})
const rules = ref<Record<string, string[]>>({})
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const errMsg = ref('')
const testResults = ref<Record<string, string>>({})

const EVENTS = [
  { key: 'archive_complete', label: '归档完成' },
  { key: 'standard_status_changed', label: '状态变更' },
  { key: 'standard_expired', label: '标准废止' },
  { key: 'standard_first_registered', label: '首次登记' },
  { key: 'check_batch_complete', label: '批次完成' },
]

const CHANNEL_META: Record<string, { label: string; icon: string }> = {
  wechat: { label: '企业微信', icon: 'pi pi-wechat' },
  telegram: { label: 'Telegram', icon: 'pi pi-telegram' },
  feishu: { label: '飞书', icon: 'pi pi-send' },
}

function _isTelegram(cfg: WechatChannelConfig | TelegramChannelConfig | FeishuChannelConfig):
  cfg is TelegramChannelConfig {
  return 'bot_token' in cfg && 'chat_id' in cfg
}

async function loadConfig() {
  loading.value = true
  errMsg.value = ''
  try {
    const cfg = await getNotificationConfig()
    enabled.value = cfg.enabled
    rules.value = cfg.rules
    for (const ch of ['wechat', 'telegram', 'feishu'] as const) {
      const sc = cfg.channels?.[ch]
      if (!sc) continue
      channels.value[ch].enabled = sc.enabled ?? false
      if (_isTelegram(sc)) {
        channels.value[ch].bot_token = sc.bot_token || ''
        channels.value[ch].chat_id = sc.chat_id || ''
      } else {
        channels.value[ch].webhook_url = sc.webhook_url || ''
      }
      channels.value[ch].events = []
      for (const ev of EVENTS) {
        if (cfg.rules?.[ev.key]?.includes(ch)) {
          channels.value[ch].events.push(ev.key)
        }
      }
    }
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '加载配置失败'
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  saved.value = false
  errMsg.value = ''
  try {
    const newRules: Record<string, string[]> = {}
    for (const ev of EVENTS) {
      newRules[ev.key] = []
      for (const ch of ['wechat', 'telegram', 'feishu']) {
        if (channels.value[ch].events.includes(ev.key)) {
          newRules[ev.key].push(ch)
        }
      }
    }
    await putNotificationConfig({
      enabled: enabled.value,
      channels: {
        wechat: {
          webhook_url: channels.value.wechat.webhook_url,
          enabled: channels.value.wechat.enabled,
        } as WechatChannelConfig,
        telegram: {
          bot_token: channels.value.telegram.bot_token,
          chat_id: channels.value.telegram.chat_id,
          enabled: channels.value.telegram.enabled,
        } as TelegramChannelConfig,
        feishu: {
          webhook_url: channels.value.feishu.webhook_url,
          enabled: channels.value.feishu.enabled,
        } as FeishuChannelConfig,
      },
      rules: newRules,
    })
    saved.value = true
    setTimeout(() => (saved.value = false), 2000)
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '保存失败'
  } finally {
    saving.value = false
  }
}

async function testChannel(ch: string) {
  testResults.value[ch] = '测试中...'
  try {
    const r = await testNotification(ch)
    testResults.value[ch] = r.ok ? '测试成功' : `失败: ${r.error || '未知'}`
  } catch (e: any) {
    testResults.value[ch] = `失败: ${e.response?.data?.error || e.message}`
  }
  setTimeout(() => delete testResults.value[ch], 4000)
}

function chStatus(ch: string): string {
  const c = channels.value[ch]
  if (!c.enabled) return '未启用'
  if (ch === 'telegram') return c.bot_token && c.chat_id ? '已配置' : '未配置'
  return c.webhook_url ? '已配置' : '未配置'
}

function chSeverity(ch: string): 'success' | 'secondary' {
  const c = channels.value[ch]
  if (!c.enabled) return 'secondary'
  if (ch === 'telegram') return c.bot_token && c.chat_id ? 'success' : 'secondary'
  return c.webhook_url ? 'success' : 'secondary'
}

onMounted(loadConfig)
</script>

<template>
  <div class="page">
    <h2 class="page-title">通知配置</h2>

    <Card class="section">
      <template #content>
        <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
        <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>

        <div class="global-row">
          <div class="switch-field">
            <ToggleSwitch v-model="enabled" />
            <label>启用通知</label>
          </div>
          <Button icon="pi pi-save" label="保存配置" :loading="saving" @click="saveConfig" />
        </div>
      </template>
    </Card>

    <Card v-for="ch in ['wechat', 'telegram', 'feishu']" :key="ch" class="section">
      <template #title>
        <div class="ch-header">
          <span>{{ CHANNEL_META[ch].label }}</span>
          <Tag :severity="chSeverity(ch)" :value="chStatus(ch)" />
        </div>
      </template>
      <template #content>
        <div class="ch-config">
          <template v-if="ch === 'telegram'">
            <div class="field">
              <label>Bot Token</label>
              <InputText v-model="channels[ch].bot_token" class="w-full" placeholder="123456:ABC-DEF" />
            </div>
            <div class="field">
              <label>Chat ID</label>
              <InputText v-model="channels[ch].chat_id" class="w-full" placeholder="-1001234567890" />
            </div>
          </template>
          <template v-else>
            <div class="field">
              <label>Webhook URL</label>
              <div class="input-row">
                <InputText v-model="channels[ch].webhook_url" class="flex-1" placeholder="https://..." />
                <Button label="测试" size="small" severity="secondary" @click="testChannel(ch)" />
              </div>
            </div>
          </template>

          <div v-if="ch !== 'telegram'" class="input-row" style="margin-top: 4px">
            <span style="flex:1" />
            <Button label="测试" size="small" severity="secondary" @click="testChannel(ch)" />
          </div>

          <div v-if="testResults[ch]" class="test-result">{{ testResults[ch] }}</div>

          <div class="switch-field" style="margin-top: 12px">
            <ToggleSwitch v-model="channels[ch].enabled" />
            <label>启用此渠道</label>
          </div>

          <div class="events-row">
            <label class="events-label">事件订阅：</label>
            <div v-for="ev in EVENTS" :key="ev.key" class="checkbox-field">
              <Checkbox v-model="channels[ch].events" :value="ev.key" :inputId="`${ch}-${ev.key}`" />
              <label :for="`${ch}-${ev.key}`">{{ ev.label }}</label>
            </div>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.page { max-width: 800px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.section { margin-bottom: 16px; }
.global-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.switch-field { display: flex; align-items: center; gap: 8px; }
.switch-field label { font-size: 13px; color: var(--text); }
.ch-header { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.ch-config { display: flex; flex-direction: column; gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; font-weight: 500; color: var(--text-dim); }
.input-row { display: flex; gap: 8px; align-items: center; }
.flex-1 { flex: 1; }
.w-full { width: 100%; }
.test-result { font-size: 12px; color: var(--text-dim); padding: 4px 0; }
.events-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 8px; }
.events-label { font-size: 13px; font-weight: 500; color: var(--text-dim); }
.checkbox-field { display: flex; align-items: center; gap: 4px; }
.checkbox-field label { font-size: 13px; color: var(--text); cursor: pointer; }
</style>
