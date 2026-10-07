<script setup lang="ts">
defineOptions({ name: 'NotificationConfig' })
// T-41 前端子批 6(2/3)：script 逻辑已抽到 `@/composables/useNotificationConfig`（见该文件头部说明）。
// 这里只做「装配 + 解构」：模板引用的名字与抽出前逐一对应；`defineExpose({ saveConfig })` 原样保留
// ⇒ 组件对外接口（defineExpose / 无 props·emits·slots）零变化。
import { useI18n } from 'vue-i18n'
import { useNotificationConfig } from '@/composables/useNotificationConfig'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import AppCalendar from '@/components/AppCalendar.vue'

const { t } = useI18n()
const {
  eventLabel,
  enabled,
  specs,
  channels,
  NOTIFY_EVENTS,
  policyLoadFailed,
  policySaveFailures,
  saved,
  errMsg,
  testResults,
  classLabel,
  EVENTS,
  channelOpen,
  fieldLabel,
  fieldPlaceholder,
  fieldBadge,
  fieldDivider,
  fieldsOfForm,
  formIssues,
  channelHint,
  statusText,
  statusSeverity,
  testChannel,
  quietHoursEnabled,
  quietHoursStart,
  quietHoursEnd,
  saveQuietHours,
  saveConfig,
} = useNotificationConfig()

defineExpose({ saveConfig })
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
          <!-- 字段表单：完全由 GET /api/notification/channels 的 spec 驱动（渠道无关）
               阶段 3 · Step 2：带 `forms` 声明的渠道**按形态分区**渲染（分区标题 + 形态提示 + 互斥校验）；
               单形态渠道保持原样（`divider_key` 分隔线机制不变，避免视觉回归） -->
          <p v-if="channelHint(ch)" style="font-size:11px;color:var(--text-dim);margin:0 0 10px">{{ channelHint(ch) }}</p>
          <template v-if="(ch.forms ?? []).length">
            <template v-for="form in (ch.forms ?? [])" :key="form.key">
              <div class="form-section">
                <div class="form-section-title">{{ t(form.label_key) }}</div>
                <div class="form-section-hint">{{ t(form.hint_key) }}</div>
              </div>
              <div v-for="f in fieldsOfForm(ch, form.key)" :key="f.name" class="field">
                <label>
                  {{ fieldLabel(f) }}
                  <span v-if="form.required.includes(f.name)" class="required">{{ t('notification.config.required') }}</span>
                  <span v-else class="optional">{{ fieldBadge(f) }}</span>
                </label>
                <Password v-if="f.type === 'password'" v-model="channels[ch.name].fields[f.name]" class="w-full" :placeholder="fieldPlaceholder(f)" size="small" toggleMask :feedback="false" />
                <InputText v-else v-model="channels[ch.name].fields[f.name]" class="w-full" :placeholder="fieldPlaceholder(f)" size="small" :type="f.type === 'text_password' ? 'password' : 'text'" />
              </div>
            </template>
            <template v-if="fieldsOfForm(ch, '').length">
              <div class="form-section">
                <div class="form-section-title">{{ t('notification.config.form.shared') }}</div>
              </div>
              <div v-for="f in fieldsOfForm(ch, '')" :key="f.name" class="field">
                <label>
                  {{ fieldLabel(f) }}
                  <span class="optional">{{ fieldBadge(f) }}</span>
                </label>
                <Password v-if="f.type === 'password'" v-model="channels[ch.name].fields[f.name]" class="w-full" :placeholder="fieldPlaceholder(f)" size="small" toggleMask :feedback="false" />
                <InputText v-else v-model="channels[ch.name].fields[f.name]" class="w-full" :placeholder="fieldPlaceholder(f)" size="small" :type="f.type === 'text_password' ? 'password' : 'text'" />
              </div>
            </template>
            <!-- 形态校验结论（缺字段 / 两者都配好时的优先级说明 / 一个都没配好） -->
            <Message v-if="formIssues(ch).length" severity="warn" :closable="false" style="margin-top:8px">
              <div v-for="(issue, idx) in formIssues(ch)" :key="idx" style="font-size:12px">{{ issue }}</div>
            </Message>
          </template>
          <template v-else>
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
/* 阶段 3 · Step 2：形态分区标题与提示（仅带 `forms` 声明的渠道出现） */
.form-section { border-top: 1px dashed var(--border); padding-top: 8px; margin: 10px 0 6px; }
.form-section-title { font-size: 12px; font-weight: 600; color: var(--text); }
.form-section-hint { font-size: 11px; color: var(--text-dim); margin-top: 2px; line-height: 1.5; }
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
