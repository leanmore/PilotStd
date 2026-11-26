<script setup lang="ts">
defineOptions({ name: 'NotificationConfig' })
// T-41 前端子批 6(2/3)：script 逻辑已抽到 `@/composables/useNotificationConfig`（见该文件头部说明）。
// 这里只做「装配 + 解构」：模板引用的名字与抽出前逐一对应；`defineExpose({ saveConfig })` 原样保留
// ⇒ 组件对外接口（defineExpose / 无 props·emits·slots）零变化。
import { useI18n } from 'vue-i18n'
import { useNotificationConfig } from '@/composables/useNotificationConfig'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import AppCalendar from '@/components/AppCalendar.vue'
import AppButton from '@/components/ui/AppButton.vue'
// DS 输入控件（模块一·C3）：原 PrimeVue InputText / Password / ToggleSwitch / Checkbox 全部收口到 App*
//   - Password 的 toggleMask（可切明文）由 <AppInput type="password" toggle-mask> 承担，
//     底层仍是 PrimeVue Password，交互形态（眼睛图标切明文）不变；
//   - InputText 的动态 :type（text_password → password）原样保留，AppInput 按 type 透传给原生 input；
//   - Checkbox 的多选语义（:value + 数组 v-model）走 AppCheckbox 的 binary=false 分支。
import AppInput from '@/components/ui/AppInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppToggle from '@/components/ui/AppToggle.vue'

const { t } = useI18n()
const {
  eventLabel,
  enabled,
  webBaseUrl,
  specs,
  channels,
  noChannelConfigured,
  NOTIFY_EVENTS,
  policyLoadFailed,
  policySaveFailures,
  saved,
  errMsg,
  testResults,
  classLabel,
  eventsOfClass,
  unmappedEvents,
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
    <!-- G-45：零渠道引导——事件仍会记录，但没有任何渠道可推送，必须明确告诉用户去哪配 -->
    <Message v-if="noChannelConfigured" severity="warn" :closable="false" class="no-channel-guide">
      <strong>{{ t('notification.config.no_channel_title') }}</strong>
      <div class="no-channel-hint">{{ t('notification.config.no_channel_hint') }}</div>
    </Message>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <!-- 吞错可见化（用户裁定）：**策略 API 失败** 与 **策略为空** 是两件事，文案必须区分、不得混为一谈 -->
    <Message v-if="policyLoadFailed" severity="warn" :closable="false">
      {{ t('notification.config.policy_load_failed') }}
    </Message>
    <Message v-if="policySaveFailures.length" severity="warn" :closable="false">
      {{ t('notification.config.policy_save_failed', { channels: policySaveFailures.join('、') }) }}
    </Message>
    <Message v-if="saved" severity="success" :closable="false">{{ t('notification.config.saved') }}</Message>

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-16);flex-wrap:wrap;gap:var(--space-8)">
      <div style="display:flex;align-items:center;gap:var(--space-8)">
        <AppToggle v-model="enabled" />
        <span style="font-size:var(--font-size-13);color:var(--text)">{{ t('notification.config.enable_all') }}</span>
      </div>
    </div>

    <div class="web-base-row">
      <label class="web-base-label">
        {{ t('notification.config.web_base_url') }}
      </label>
      <AppInput
        v-model="webBaseUrl"
        class="w-full"
        :placeholder="t('notification.config.web_base_url_placeholder')"
      />
      <div class="web-base-hint">{{ t('notification.config.web_base_url_hint') }}</div>
    </div>

    <div class="channel-grid">
      <div v-for="ch in specs" :key="ch.name" class="collapsible-card">
        <div class="collapsible-header" @click="channelOpen[ch.name] = !channelOpen[ch.name]">
          <div style="display:flex;align-items:center;gap:var(--space-8)">
            <i :class="ch.icon" style="font-size:var(--font-size-16);color:var(--primary)" />
            <span class="collapsible-title">{{ t(ch.label_key) }}</span>
          </div>
          <div style="display:flex;align-items:center;gap:var(--space-8)">
            <Tag :severity="statusSeverity(ch)" :value="statusText(ch)" />
            <i :class="channelOpen[ch.name] ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
          </div>
        </div>
        <transition name="collapsible">
          <div v-show="channelOpen[ch.name]" class="collapsible-content">
          <!-- 字段表单：完全由 GET /api/notification/channels 的 spec 驱动（渠道无关）
               阶段 3 · Step 2：带 `forms` 声明的渠道**按形态分区**渲染（分区标题 + 形态提示 + 互斥校验）；
               单形态渠道保持原样（`divider_key` 分隔线机制不变，避免视觉回归） -->
          <p v-if="channelHint(ch)" style="font-size:var(--font-size-11);color:var(--text-dim);margin:0 0 var(--space-10)">{{ channelHint(ch) }}</p>
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
                <!-- 密码字段：AppInput type="password" + toggle-mask ⇒ 底层仍是 PrimeVue Password，
                     「眼睛图标切明文」与 :feedback="false"（不显示强度浮层）逐字保留 -->
                <AppInput
                  v-if="f.type === 'password'"
                  v-model="channels[ch.name].fields[f.name]"
                  class="w-full"
                  :placeholder="fieldPlaceholder(f)"
                  type="password"
                  toggle-mask
                />
                <!-- 其余字段：动态 type 原样保留（text_password → password，否则 text） -->
                <AppInput
                  v-else
                  v-model="channels[ch.name].fields[f.name]"
                  class="w-full"
                  :placeholder="fieldPlaceholder(f)"
                  :type="f.type === 'text_password' ? 'password' : 'text'"
                />
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
                <AppInput
                  v-if="f.type === 'password'"
                  v-model="channels[ch.name].fields[f.name]"
                  class="w-full"
                  :placeholder="fieldPlaceholder(f)"
                  type="password"
                  toggle-mask
                />
                <AppInput
                  v-else
                  v-model="channels[ch.name].fields[f.name]"
                  class="w-full"
                  :placeholder="fieldPlaceholder(f)"
                  :type="f.type === 'text_password' ? 'password' : 'text'"
                />
              </div>
            </template>
            <!-- 形态校验结论（缺字段 / 两者都配好时的优先级说明 / 一个都没配好） -->
            <Message v-if="formIssues(ch).length" severity="warn" :closable="false" style="margin-top:var(--space-8)">
              <div v-for="(issue, idx) in formIssues(ch)" :key="idx" style="font-size:var(--font-size-12)">{{ issue }}</div>
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
                <AppInput
                  v-if="f.type === 'password'"
                  v-model="channels[ch.name].fields[f.name]"
                  class="w-full"
                  :placeholder="fieldPlaceholder(f)"
                  type="password"
                  toggle-mask
                />
                <AppInput
                  v-else
                  v-model="channels[ch.name].fields[f.name]"
                  class="w-full"
                  :placeholder="fieldPlaceholder(f)"
                  :type="f.type === 'text_password' ? 'password' : 'text'"
                />
              </div>
            </template>
          </template>
          <div style="margin-top:var(--space-8)">
<AppButton
              :label="t('notification.config.test')"
              @click="testChannel(ch)"
              size="s"
              type="secondary"
            />
          </div>

          <div v-if="testResults[ch.name]" class="test-result">{{ testResults[ch.name] }}</div>

          <div style="display:flex;align-items:center;gap:var(--space-8);margin-top:var(--space-10)">
            <AppToggle v-model="channels[ch.name].enabled" />
            <label style="font-size:var(--font-size-12);color:var(--text-dim)">{{ t('notification.config.enable_channel') }}</label>
          </div>

          <!-- ① 类别层（一级分类）：订阅主入口；非空时后端读侧优先用它 -->
          <div class="events-row">
            <label class="events-label">{{ t('notification.config.classes_label', { count: NOTIFY_EVENTS.length }) }}</label>
            <div v-for="cls in NOTIFY_EVENTS" :key="cls" class="checkbox-field">
              <!-- 多选（binary=false）：:value 作为选项值，v-model 绑数组 —— 与 PrimeVue Checkbox 语义一致 -->
              <AppCheckbox v-model="channels[ch.name].eventClasses" :value="cls" :input-id="`${ch.name}-cls-${cls}`" />
              <label :for="`${ch.name}-cls-${cls}`">{{ classLabel(cls) }}</label>
            </div>
            <p style="font-size:var(--font-size-11);color:var(--text-dim);margin:var(--space-4) 0 0">
              {{ t('notification.config.classes_hint') }}
            </p>
          </div>

          <!-- ② 高级层（二级分类）：按一级类别分组，避免平铺成"大补丁" -->
          <details class="events-advanced">
            <summary style="font-size:var(--font-size-12);color:var(--text-dim);cursor:pointer">
              {{ t('notification.config.advanced_label', { count: EVENTS.length }) }}
            </summary>
            <div v-for="cls in NOTIFY_EVENTS" :key="`group-${cls}`" v-show="eventsOfClass(cls).length" class="class-group">
              <div class="class-group-title">{{ classLabel(cls) }}（{{ eventsOfClass(cls).length }}）</div>
              <div class="events-row">
                <div v-for="ev in eventsOfClass(cls)" :key="ev" class="checkbox-field">
                  <AppCheckbox v-model="channels[ch.name].events" :value="ev" :input-id="`${ch.name}-${ev}`" />
                  <label :for="`${ch.name}-${ev}`">{{ eventLabel(ev) }}</label>
                </div>
              </div>
            </div>
            <div v-if="unmappedEvents().length" class="class-group">
              <div class="class-group-title">{{ t('notification.config.advanced_other') }}</div>
              <div class="events-row">
                <div v-for="ev in unmappedEvents()" :key="ev" class="checkbox-field">
                  <AppCheckbox v-model="channels[ch.name].events" :value="ev" :input-id="`${ch.name}-${ev}`" />
                  <label :for="`${ch.name}-${ev}`">{{ eventLabel(ev) }}</label>
                </div>
              </div>
            </div>
          </details>
          </div>
        </transition>
      </div>
    </div>

    <!-- 静音时段（全局通知配置） -->
    <div class="collapsible-card" style="margin-top:var(--space-16)">
      <div class="collapsible-header" style="cursor:default">
        <div style="display:flex;align-items:center;gap:var(--space-8)">
          <i class="pi pi-moon" style="font-size:var(--font-size-16);color:var(--primary)" />
          <span class="collapsible-title">{{ t('notification.config.quiet_hours.title') }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:var(--space-8)">
          <Tag :severity="quietHoursEnabled ? 'success' : 'secondary'" :value="quietHoursEnabled ? t('notification.config.quiet_hours.enabled') : t('notification.config.quiet_hours.disabled')" />
        </div>
      </div>
      <div class="collapsible-content">
        <div class="config-row">
          <label>{{ t('notification.config.quiet_hours.enable') }}</label>
          <AppToggle v-model="quietHoursEnabled" @change="saveQuietHours" />
          <span style="font-size:var(--font-size-12);color:var(--text-dim);margin-left:var(--space-8)">
            {{ t('notification.config.quiet_hours.hint') }}
          </span>
        </div>
        <div v-if="quietHoursEnabled" class="config-row" style="margin-top:var(--space-8)">
          <label>{{ t('notification.config.quiet_hours.start') }}</label>
          <AppCalendar v-model="quietHoursStart" timeOnly hourFormat="24" @update:model-value="saveQuietHours" />
          <label style="margin-left:var(--space-16)">{{ t('notification.config.quiet_hours.end') }}</label>
          <AppCalendar v-model="quietHoursEnd" timeOnly hourFormat="24" @update:model-value="saveQuietHours" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 站内访问地址（全局设置，位于渠道卡片之上） */
.web-base-row {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: var(--space-12);
  margin-bottom: var(--space-16);
  background: var(--bg);
}
.web-base-label {
  display: block;
  font-size: var(--font-size-12);
  color: var(--text);
  margin-bottom: var(--space-6);
}
.web-base-hint {
  margin-top: var(--space-6);
  font-size: var(--font-size-11);
  color: var(--text-dim);
}
.channel-grid { display: flex; flex-direction: column; gap: var(--space-12); }

.collapsible-card {
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs); overflow: hidden; transition: all var(--transition);
}
.collapsible-card:hover { box-shadow: var(--shadow-sm); }
.collapsible-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-14) var(--space-18); cursor: pointer; user-select: none;
  background: linear-gradient(180deg, var(--surface), var(--surface-raised));
  border-bottom: 1px solid transparent; transition: all var(--transition);
}
.collapsible-header:hover { background: var(--selected); border-bottom-color: var(--border); }

.collapsible-title { font-size: var(--font-size-14); font-weight: var(--font-weight-bold); color: var(--text-heading); }

.collapsible-icon {
  font-size: var(--font-size-13); color: var(--text-dim); transition: transform var(--transition);
  padding: var(--space-2); border-radius: var(--radius-sm);
}
.collapsible-header:hover .collapsible-icon { color: var(--primary); background: var(--primary-bg); }
.collapsible-content { padding: var(--space-16) var(--space-18); }
/* collapsible 过渡统一由 views/settings/shared.css 提供（全站一份真相）；
   本组件不再重复定义 —— 原先这里多一份 padding 过渡，导致同一交互在两个页面观感不一致。 */

.field { margin-bottom: var(--space-8); }
.field label { display: block; font-size: var(--font-size-12); color: var(--text-secondary); margin-bottom: var(--space-4); }
.required { color: var(--danger); font-size: var(--font-size-10); }
.optional { color: var(--text-dim); font-size: var(--font-size-10); }
.field-sep { font-size: var(--font-size-11); color: var(--text-dim); border-top: 1px dashed var(--border); padding-top: var(--space-8); margin: var(--space-8) 0 var(--space-6); }
/* 阶段 3 · Step 2：形态分区标题与提示（仅带 `forms` 声明的渠道出现） */
.form-section { border-top: 1px dashed var(--border); padding-top: var(--space-8); margin: var(--space-10) 0 var(--space-6); }
.form-section-title { font-size: var(--font-size-12); font-weight: var(--font-weight-semibold); color: var(--text); }
.form-section-hint { font-size: var(--font-size-11); color: var(--text-dim); margin-top: var(--space-2); line-height: var(--line-height-normal); }
.w-full { width: 100%; }
.flex-1 { flex: 1; }
.test-result { font-size: var(--font-size-12); margin-top: var(--space-6); color: var(--text-dim); }
.events-row { margin-top: var(--space-10); border-top: 1px solid var(--border-light); padding-top: var(--space-8); }
.events-label { font-size: var(--font-size-12); color: var(--text-secondary); margin-bottom: var(--space-4); display: block; }
.checkbox-field { display: inline-flex; align-items: center; gap: var(--space-4); margin-right: var(--space-12); margin-top: var(--space-4); }
.checkbox-field label { font-size: var(--font-size-12); color: var(--text); }
.class-group { margin-top: var(--space-10); }
.class-group-title { font-size: var(--font-size-12); font-weight: var(--font-weight-semibold); color: var(--text-heading); margin: var(--space-6) 0 var(--space-2); }
.events-check-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-4) var(--space-8); margin-top: var(--space-6);
}
.config-row {
  display: flex; align-items: center; gap: var(--space-8); flex-wrap: wrap;
}
.config-row label { font-size: var(--font-size-13); color: var(--text); }
</style>
