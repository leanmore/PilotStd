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
  getNotificationChannels, getNotificationSpec, getNotificationPolicies, putNotificationPolicy,
  type ChannelFieldSpec, type ChannelSpec, type NotificationConfigUpdate,
} from '@/api/notification'

const { t, te } = useI18n()

/** 事件类型 → i18n key（notification.event.<type>，与日志页共用同一套文案） */
function eventLabel(type: string): string {
  const key = `notification.event.${type}`
  return te(key) ? t(key) : type
}

/**
 * 表单状态：字段集合由渠道 spec 动态决定（不再是"每渠道 8 字段超集"的硬编码），
 * 故用索引签名承载；`enabled`/`events`/`eventClasses` 是不属于 spec 字段的固定槽位。
 *
 * **两层订阅（阶段 4 · P6 · 4b）**：
 * · `eventClasses`＝**类别层**（10 类，主入口；非空时后端读侧优先用它）；
 * · `events`＝**高级层**（41 个业务事件，保留原有表达力）。
 * 二者在 UI 上并列呈现、在后端互不覆盖。
 */
interface ChannelFormState {
  enabled: boolean
  events: string[]
  eventClasses: string[]
  /** 渠道字段值（键为 spec 的 field.name）；与 enabled/events/eventClasses 分离以保持类型精确 */
  fields: Record<string, string>
}

const enabled = ref(false)
/** 渠道元数据（唯一来源 = 后端 `channel_spec.py`，经 `GET /api/notification/channels` 下发） */
const specs = ref<ChannelSpec[]>([])
const channels = ref<Record<string, ChannelFormState>>({})
const specHash = ref('')
/** 类别层清单（10 类 `notify_event`）+ 事件→类别映射：与渠道元数据同源下发（进 spec_hash ⇒ 层变即缓存失效） */
const NOTIFY_EVENTS = ref<string[]>([])
const EVENT_CLASS_MAP = ref<Record<string, string>>({})
/** 策略层加载状态：区分"策略 API 失败"与"策略为空"（用户裁定：吞错必须可见，且两者不可混淆） */
const policyLoadFailed = ref(false)
/** 保存时策略层写入失败的渠道名（非空 ⇒ UI 明确提示"未落库"，不谎报已保存） */
const policySaveFailures = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const errMsg = ref('')
const testResults = ref<Record<string, string>>({})

/**
 * 类别层标签：文案 key = `notification.class.<cls>`（与后端 `mapping.NOTIFY_EVENTS` 的 10 类一一对应）。
 * 与 `eventLabel` 同款兜底：i18n 缺键时回退显示原始类别名，**不显示空白**。
 */
function classLabel(cls: string): string {
  const key = `notification.class.${cls}`
  return te(key) ? t(key) : cls
}

// 可订阅的事件类型（后端 event_type 原值）；文案 key = notification.event.<type>（与日志页共用）
// 可订阅的事件类型（**来自后端事件规格**，D5：前端零硬编码）；
// 文案 key = notification.event.<type>（与日志页共用）
const EVENTS = ref<string[]>([])

/** 渠道折叠状态（按 spec 的渠道名动态构建，不再硬编码 4 键） */
const channelOpen = ref<Record<string, boolean>>({})

// ── spec 驱动的渲染辅助（模板直接调用，避免在模板里写渠道名分支）──

/** 标签：前端 locales 优先（`label_key`）→ 字面量（裁决 N6 保持英文的 4 处即走此路） */
function fieldLabel(f: ChannelFieldSpec): string {
  if (f.label_key && te(f.label_key)) return t(f.label_key)
  return f.label || f.label_key || f.name
}

/** 输入提示：优先 i18n 键，其次字面量 */
function fieldPlaceholder(f: ChannelFieldSpec): string {
  if (f.placeholder_key && te(f.placeholder_key)) return t(f.placeholder_key)
  return f.placeholder
}

/** 标签旁的徽标：优先 spec 声明的键（"群机器人"／"可选"／"可选（简）"），无则按必填态取默认 */
function fieldBadge(f: ChannelFieldSpec): string {
  if (f.badge_key && te(f.badge_key)) return t(f.badge_key)
  return t(f.required ? 'notification.config.required' : 'notification.config.optional')
}

/** 字段前的分段标签（如企微"自建应用"分隔） */
function fieldDivider(f: ChannelFieldSpec): string {
  return f.divider_key && te(f.divider_key) ? t(f.divider_key) : ''
}

/** 渠道级提示段落 */
function channelHint(spec: ChannelSpec): string {
  return spec.hint_key && te(spec.hint_key) ? t(spec.hint_key) : ''
}

/**
 * "已配置"判定：按 spec 的 `status_rule` 分支求值（渠道特有逻辑已声明化，前端不再有 if/else）。
 * 返回文案；未启用时按 `disabled` 处理（与改造前一致）。
 */
function statusText(spec: ChannelSpec): string {
  const form = channels.value[spec.name]
  if (!form || !form.enabled) return t('notification.config.status.disabled')
  for (const branch of spec.status_rule.branches) {
    const hit = branch.all_of.every((k) => (form.fields[k] ?? '').trim() !== '')
    if (hit) return te(branch.label_key) ? t(branch.label_key) : branch.label_key
  }
  return t(spec.status_rule.fallback_key)
}

/** 标签颜色：未启用 secondary；命中任一分支 success；否则（待配置）secondary */
function statusSeverity(spec: ChannelSpec): 'success' | 'secondary' {
  const form = channels.value[spec.name]
  if (!form || !form.enabled) return 'secondary'
  for (const branch of spec.status_rule.branches) {
    const hit = branch.all_of.every((k) => (form.fields[k] ?? '').trim() !== '')
    if (hit) return 'success'
  }
  return 'secondary'
}

/**
 * 拉取渠道元数据并按 spec 重建空表单。
 * 同一 `spec_hash` 且已建表时复用（内容级缓存失效）；`saveConfig` 后调用本函数即可，
 * 哈希未变时不会重建（避免清空用户正在编辑的内容）。
 */
async function loadChannelSpecs(force = false) {
  const resp = await getNotificationChannels('/settings')
  EVENTS.value = (await getNotificationSpec('/settings')).events
  if (!force && specHash.value === resp.spec_hash && specs.value.length) return
  specHash.value = resp.spec_hash
  specs.value = resp.channels
  // 层级结构随渠道元数据同源下发；它**进了 spec_hash** ⇒ 层变时上面的早退不会命中（表单会重建）
  NOTIFY_EVENTS.value = resp.notify_events ?? []
  EVENT_CLASS_MAP.value = resp.event_class_map ?? {}
  const next: Record<string, ChannelFormState> = {}
  const open: Record<string, boolean> = {}
  for (const spec of resp.channels) {
    const form: ChannelFormState = {
      enabled: spec.enabled_default,
      events: [],
      eventClasses: [],
      fields: {},
    }
    for (const f of spec.fields) form.fields[f.name] = ''
    next[spec.name] = form
    open[spec.name] = channelOpen.value[spec.name] ?? false
  }
  channels.value = next
  channelOpen.value = open
}

async function loadConfig() {
  loading.value = true; errMsg.value = ''
  try {
    // 先按 spec 建表（渠道与字段均来自后端声明），再回填用户配置
    await loadChannelSpecs()
    const cfg = await getNotificationConfig('/settings')
    enabled.value = cfg.enabled
    const rawChannels = (cfg.channels ?? {}) as unknown as Record<string, Record<string, unknown>>
    for (const spec of specs.value) {
      const form = channels.value[spec.name]
      const sc = rawChannels[spec.name]
      if (!form || !sc) continue
      form.enabled = Boolean(sc.enabled ?? false)
      for (const f of spec.fields) form.fields[f.name] = String(sc[f.name] ?? '')
      const events: string[] = []
      for (const ev of EVENTS.value) {
        if (cfg.rules?.[ev]?.includes(spec.name)) events.push(ev)
      }
      form.events = events
    }

    // 尝试从策略 API 加载**两层**订阅（优先于 config.json rules）
    // **吞错可见化（用户裁定）**：失败时置 `policyLoadFailed` 并 `console.warn`，
    // 但**不**把它与"策略为空"混为一谈——前者是故障、后者是正常状态。
    policyLoadFailed.value = false
    try {
      const { policies } = await getNotificationPolicies()
      for (const p of policies ?? []) {
        const form = channels.value[p.channel]
        if (!form) continue
        form.events = [...(p.events ?? [])]
        form.eventClasses = [...(p.event_classes ?? [])]
      }
    } catch (e: unknown) {
      policyLoadFailed.value = true
      // 开发者日志用 ASCII：G-040（前端 i18n 硬编码检查）只允许用户可见文案走 t()，
      // 这条是给开发者看的诊断 ⇒ 不进 locales（用户可见提示见模板里的 policy_load_failed）。
      console.warn('[notification] policy API read failed; fell back to config.json rules', e)
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    errMsg.value = err.response?.data?.error || t('notification.config.load_failed')
  } finally { loading.value = false }
}

async function saveConfig() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    const newRules: Record<string, string[]> = {}
    for (const ev of EVENTS.value) {
      newRules[ev] = specs.value
        .filter((spec) => ((channels.value[spec.name]?.events ?? []) as string[]).includes(ev))
        .map((spec) => spec.name)
    }
    // P1 修复：**需掩码**字段增量提交——掩码回显值（含 *）或空值不提交，保留 DB 原值。
    // "是否需掩码"来自 spec 的 `field.mask`（后端同一份声明），不再硬编码字段名清单。
    const cleanChannel = (spec: ChannelSpec): Record<string, unknown> => {
      const form = channels.value[spec.name] ?? { enabled: false, events: [], eventClasses: [], fields: {} }
      const cleaned: Record<string, unknown> = {}
      for (const f of spec.fields) {
        const v = form.fields[f.name]
        if (f.mask) {
          if (typeof v === 'string' && v.trim() !== '' && !v.includes('*')) cleaned[f.name] = v
        } else {
          cleaned[f.name] = v
        }
      }
      cleaned.enabled = form.enabled
      cleaned.events = form.events
      return cleaned
    }
    const payloadChannels: Record<string, Record<string, unknown>> = {}
    for (const spec of specs.value) payloadChannels[spec.name] = cleanChannel(spec)
    await putNotificationConfig({
      enabled: enabled.value,
      channels: payloadChannels as NotificationConfigUpdate['channels'],
      rules: newRules,
    })
    // 同时保存**两层**订阅到策略表（按 spec 的渠道名遍历）
    // **吞错可见化（用户裁定）**：失败不再静默——`console.warn` + 收集失败渠道名，
    // 由模板显示"未落库"提示，避免"看起来保存成功、实际类别层没落库"。
    policySaveFailures.value = []
    for (const spec of specs.value) {
      const form = channels.value[spec.name]
      try {
        await putNotificationPolicy({
          channel: spec.name,
          events: (form?.events ?? []) as string[],
          event_classes: (form?.eventClasses ?? []) as string[],
        })
      } catch (e: unknown) {
        policySaveFailures.value = [...policySaveFailures.value, spec.name]
        // ASCII 开发者日志（同 policyLoadFailed 的理由）；用户可见提示走 i18n 的 policy_save_failed
        console.warn(`[notification] policy layer write failed for channel ${spec.name}`, e)
      }
    }
    // spec 可能已变（哈希变则重建表单并回填）；未变时本调用不做任何事
    await loadChannelSpecs()
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    errMsg.value = err.response?.data?.error || t('common.save_failed')
  } finally { saving.value = false }
}

defineExpose({ saveConfig })

async function testChannel(spec: ChannelSpec) {
  const ch = spec.name
  testResults.value[ch] = t('notification.config.testing')
  try {
    // 测试参数 = 该渠道 spec 声明的全部字段（渠道无关；后端按渠道只取自己需要的键，
    // 多余键被忽略——见 _format_utils.do_test_send 的按渠道取值）
    const form = channels.value[ch] ?? { enabled: false, events: [], fields: {} }
    const params: Record<string, string> = {}
    for (const f of spec.fields) params[f.name] = form.fields[f.name] ?? ''
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
    <!-- 吞错可见化（用户裁定）：**策略 API 失败** 与 **策略为空** 是两件事，文案必须区分、不得混为一谈 -->
    <Message v-if="policyLoadFailed" severity="warn" :closable="false">
      {{ t('notification.config.policy_load_failed') }}
    </Message>
    <Message v-if="policySaveFailures.length" severity="warn" :closable="false">
      {{ t('notification.config.policy_save_failed', { channels: policySaveFailures.join('、') }) }}
    </Message>
    <Message v-if="saved" severity="success" :closable="false">{{ t('notification.config.saved') }}</Message>

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <ToggleSwitch v-model="enabled" />
        <span style="font-size:13px;color:var(--text)">{{ t('notification.config.enable_all') }}</span>
      </div>
    </div>

    <div class="channel-grid">
      <div v-for="ch in specs" :key="ch.name" class="collapsible-card">
        <div class="collapsible-header" @click="channelOpen[ch.name] = !channelOpen[ch.name]">
          <div style="display:flex;align-items:center;gap:8px">
            <i :class="ch.icon" style="font-size:16px;color:var(--primary)" />
            <span class="collapsible-title">{{ t(ch.label_key) }}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <Tag :severity="statusSeverity(ch)" :value="statusText(ch)" />
            <i :class="channelOpen[ch.name] ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
          </div>
        </div>
        <transition name="collapsible">
          <div v-show="channelOpen[ch.name]" class="collapsible-content">
          <!-- 字段表单：完全由 GET /api/notification/channels 的 spec 驱动（渠道无关） -->
          <p v-if="channelHint(ch)" style="font-size:11px;color:var(--text-dim);margin:0 0 10px">{{ channelHint(ch) }}</p>
          <template v-for="f in ch.fields" :key="f.name">
            <div v-if="fieldDivider(f)" class="field-sep">{{ fieldDivider(f) }}</div>
            <div class="field">
              <label>
                {{ fieldLabel(f) }}
                <span v-if="f.required" class="required">{{ t('notification.config.required') }}</span>
                <span v-else class="optional">{{ fieldBadge(f) }}</span>
              </label>
              <Password v-if="f.type === 'password'" v-model="channels[ch.name].fields[f.name]" class="w-full" :placeholder="fieldPlaceholder(f)" size="small" toggleMask :feedback="false" />
              <InputText v-else v-model="channels[ch.name].fields[f.name]" class="w-full" :placeholder="fieldPlaceholder(f)" size="small" :type="f.type === 'text_password' ? 'password' : 'text'" />
            </div>
          </template>
          <div style="margin-top:8px">
            <Button :label="t('notification.config.test')" size="small" severity="secondary" @click="testChannel(ch)" />
          </div>

          <div v-if="testResults[ch.name]" class="test-result">{{ testResults[ch.name] }}</div>

          <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
            <ToggleSwitch v-model="channels[ch.name].enabled" />
            <label style="font-size:12px;color:var(--text-dim)">{{ t('notification.config.enable_channel') }}</label>
          </div>

          <!-- ① 类别层（10 类）：订阅主入口；非空时后端读侧优先用它 -->
          <div class="events-row">
            <label class="events-label">{{ t('notification.config.classes_label') }}</label>
            <div v-for="cls in NOTIFY_EVENTS" :key="cls" class="checkbox-field">
              <Checkbox v-model="channels[ch.name].eventClasses" :value="cls" :input-id="`${ch.name}-cls-${cls}`" />
              <label :for="`${ch.name}-cls-${cls}`">{{ classLabel(cls) }}</label>
            </div>
            <p style="font-size:11px;color:var(--text-dim);margin:4px 0 0">
              {{ t('notification.config.classes_hint') }}
            </p>
          </div>

          <!-- ② 高级层（41 个业务事件）：默认折叠，保留原有表达力 -->
          <details class="events-advanced">
            <summary style="font-size:12px;color:var(--text-dim);cursor:pointer">
              {{ t('notification.config.advanced_label') }}
            </summary>
            <div class="events-row">
              <label class="events-label">{{ t('notification.config.events_label') }}</label>
              <div v-for="ev in EVENTS" :key="ev" class="checkbox-field">
                <Checkbox v-model="channels[ch.name].events" :value="ev" :input-id="`${ch.name}-${ev}`" />
                <label :for="`${ch.name}-${ev}`">{{ eventLabel(ev) }}</label>
              </div>
            </div>
          </details>
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
