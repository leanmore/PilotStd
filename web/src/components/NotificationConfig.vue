<script setup lang="ts">
// NotificationConfig.vue — 通知配置组件（从 NotificationsView 提取，增加钉钉渠道）
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import {
  getNotificationConfig,
  putNotificationConfig,
  testNotification,
  type WechatChannelConfig,
  type TelegramChannelConfig,
  type FeishuChannelConfig,
  type DingTalkChannelConfig,
} from '@/api/notification'

// 渠道编辑结构（本地表单绑定）
interface ChannelFormState {
  enabled: boolean
  webhook_url: string
  bot_token: string
  chat_id: string
  secret: string    // 钉钉加签
  events: string[]
}

const enabled = ref(false)
const channels = ref<Record<string, ChannelFormState>>({
  wechat:   { enabled: true,  webhook_url: '', bot_token: '', chat_id: '', secret: '', events: [] },
  telegram: { enabled: false, webhook_url: '', bot_token: '', chat_id: '', secret: '', events: [] },
  feishu:   { enabled: false, webhook_url: '', bot_token: '', chat_id: '', secret: '', events: [] },
  dingtalk: { enabled: false, webhook_url: '', bot_token: '', chat_id: '', secret: '', events: [] },
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
  { key: 'wechat',   label: '企业微信', icon: 'pi pi-comments', fields: ['webhook_url'] },
  { key: 'telegram', label: 'Telegram',  icon: 'pi pi-send',    fields: ['bot_token', 'chat_id'] },
  { key: 'feishu',   label: '飞书',     icon: 'pi pi-book',    fields: ['webhook_url'] },
  { key: 'dingtalk', label: '钉钉',     icon: 'pi pi-bolt',    fields: ['webhook_url', 'secret'] },
]

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
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    const newRules: Record<string, string[]> = {}
    for (const ev of EVENTS) {
      newRules[ev.key] = []
      for (const ch of ['wechat', 'telegram', 'feishu', 'dingtalk']) {
        if (channels.value[ch].events.includes(ev.key)) {
          newRules[ev.key].push(ch)
        }
      }
    }
    await putNotificationConfig({
      enabled: enabled.value,
      channels: {
        wechat: { webhook_url: channels.value.wechat.webhook_url, enabled: channels.value.wechat.enabled } as WechatChannelConfig,
        telegram: { bot_token: channels.value.telegram.bot_token, chat_id: channels.value.telegram.chat_id, enabled: channels.value.telegram.enabled } as TelegramChannelConfig,
        feishu: { webhook_url: channels.value.feishu.webhook_url, enabled: channels.value.feishu.enabled } as FeishuChannelConfig,
        dingtalk: { webhook_url: channels.value.dingtalk.webhook_url, secret: channels.value.dingtalk.secret, enabled: channels.value.dingtalk.enabled } as DingTalkChannelConfig,
      },
      rules: newRules,
    })
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch (e: any) {
    errMsg.value = e.response?.data?.error || '保存失败'
  } finally {
    saving.value = false
  }
}

defineExpose({ saveConfig })

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
  if (ch === 'dingtalk') return c.webhook_url ? '已配置' : '未配置'
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
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>

    <!-- 全局开关 -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <ToggleSwitch v-model="enabled" />
        <span style="font-size:13px;color:var(--text)">启用通知</span>
      </div>
    </div>

    <!-- 渠道卡片网格 -->
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
          <!-- Telegram: Bot Token + Chat ID -->
          <template v-if="ch.key === 'telegram'">
            <div class="field">
              <label>Bot Token</label>
              <InputText v-model="channels[ch.key].bot_token" class="w-full" placeholder="123456:ABC-DEF" size="small" />
            </div>
            <div class="field">
              <label>Chat ID</label>
              <InputText v-model="channels[ch.key].chat_id" class="w-full" placeholder="-1001234567890" size="small" />
            </div>
          </template>
          <!-- 企业微信 / 飞书 / 钉钉：Webhook URL -->
          <template v-else>
            <div class="field">
              <label>Webhook URL</label>
              <div style="display:flex;gap:6px">
                <InputText v-model="channels[ch.key].webhook_url" class="flex-1" placeholder="https://..." size="small" />
                <Button label="测试" size="small" severity="secondary" @click="testChannel(ch.key)" />
              </div>
            </div>
            <!-- 钉钉：secret 可选 -->
            <div v-if="ch.key === 'dingtalk'" class="field">
              <label>加签 Secret（可选）</label>
              <InputText v-model="channels[ch.key].secret" class="w-full" placeholder="SEC..." size="small" />
            </div>
          </template>

          <div v-if="testResults[ch.key]" class="test-result">{{ testResults[ch.key] }}</div>

          <!-- 启用开关 -->
          <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
            <ToggleSwitch v-model="channels[ch.key].enabled" />
            <label style="font-size:12px;color:var(--text-dim)">启用此渠道</label>
          </div>

          <!-- 事件订阅 -->
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
.channel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
}
.channel-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.ch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}
.field label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
}

.flex-1 { flex: 1; }
.w-full { width: 100%; }

.test-result {
  font-size: 12px;
  color: var(--text-dim);
  padding: 4px 0;
}

.events-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.events-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
}
.checkbox-field {
  display: flex;
  align-items: center;
  gap: 4px;
}
.checkbox-field label {
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
}
</style>
