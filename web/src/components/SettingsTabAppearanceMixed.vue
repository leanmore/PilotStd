<script setup lang="ts">
/**
 * SettingsTabAppearanceMixed.vue — 界面设置 Tab（混合布局）。
 *
 * 三部分内容：
 *   1. login_bg 上传区域 — 手写 getp/setp（需要 flex 布局 + 上传按钮）
 *   2. 公告自动检查  — Schema 驱动 DynamicSettingField
 *   3. 主题 / 语言   — Pinia store 管理
 */
import { computed, inject, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { THEMES } from '@/config/themes'
import { useAppStore } from '@/stores/app'
import AppInput from '@/components/ui/AppInput.vue'
import AppSelect from '@/components/ui/AppSelect.vue'

defineOptions({ name: 'SettingsTabAppearanceMixed' })

const { t } = useI18n()
const store = useAppStore()
const getp = inject<(path: string, def?: unknown) => unknown>('settingsGetp')!
const setp = inject<(path: string, val: unknown) => void>('settingsSetp')!

const fileError = ref('')

/**
 * login_bg 文本输入的回写逻辑（原 handleBgInput 的语义迁移）。
 *
 * 原实现是原生 `<input :value @input>`：读 `event.target.value`，检测到 `file://`
 * 时还要 `target.value = ''` 手动清空 DOM，否则浏览器会把用户刚粘贴的本地路径留在框里。
 * 换成 AppInput 后是**受控**写法（:model-value 绑 getp('appearance.login_bg')）：
 * 校验失败时 setp 写回 ''，model-value 随之变为 ''，组件自动重渲染成空框 ——
 * DOM 清空由受控绑定承担，不再需要手动碰 target.value。
 *
 * 入参放宽到 string | number | null：AppInput 的 update:modelValue 是
 * 「string（文本分叉）/ number|null（数字分叉）」的重载联合，文本场景实际只会给 string，
 * 这里按 typeof 收窄，既满足类型契约又不改变行为。
 */
function onBgInput(val: string | number | null) {
  const s = typeof val === 'string' ? val : ''
  if (s.startsWith('file://')) {
    fileError.value = t('settings.appearance.unsupported_local_path')
    setp('appearance.login_bg', '')
  } else {
    fileError.value = ''
    setp('appearance.login_bg', s)
  }
}

const props = defineProps<{
  selectedLocale: string
  localeOptions: { label: string; value: string }[]
  onUploadBg: (e: Event) => void
}>()

const emit = defineEmits<{
  (e: 'update:selectedLocale', val: string): void
  (e: 'localeChange'): void
}>()

const themeList = computed(() => Object.values(THEMES))

function setTheme(v: string) { store.theme = v }

function handleLocaleChange(val: unknown) {
  const locale = String(val ?? '')
  emit('update:selectedLocale', locale)
  emit('localeChange')
}
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">{{ t('settings.appearance.title') }}</div>
    <div class="form-grid">
      <!-- 1. login_bg 上传区块 -->
      <label for="login-bg-input">{{ t('settings.appearance.login_bg') }}</label>
      <div style="display:flex;gap:var(--space-8)">
        <AppInput
          id="login-bg-input"
          :model-value="String(getp('appearance.login_bg') ?? '')"
          @update:model-value="onBgInput"
          style="flex:1" :placeholder="t('settings.appearance.bg_placeholder')"
        />
        <label class="upload-btn">
          <i class="pi pi-upload" /> {{ t('settings.appearance.upload') }}
          <!-- 结构性控件（隐藏上传域）：必须保留 display:none 的 style 与原生 change 事件，
               故走 AppInput bare —— 零样式透传，不施加任何 DS 外观，视觉与替换前完全一致。 -->
          <AppInput bare type="file" accept="image/*" style="display:none" @change="props.onUploadBg" />
        </label>
      </div>
      <span v-if="fileError" class="field-error" style="grid-column:2">{{ fileError }}</span>
      <span class="text-dim" style="font-size:var(--font-size-11);grid-column:2">{{ t('settings.appearance.upload_hint') }}</span>

      <!-- 2. 主题（分组标题 + Pinia store 管理） -->
      <div class="fieldset-gap" style="grid-column: 1 / -1" />
      <label class="fieldset-label" id="theme-label" style="grid-column: unset">{{ t('settings.appearance.theme') }}</label>
      <div class="theme-options" role="radiogroup" aria-labelledby="theme-label">
        <div
          v-for="th in themeList"
          :key="th.id"
          class="theme-option"
          :class="{ active: store.theme === th.id }"
          role="radio"
          :aria-checked="store.theme === th.id"
          tabindex="0"
          @click="setTheme(th.id)"
          @keydown.enter="setTheme(th.id)"
          @keydown.space.prevent="setTheme(th.id)"
        >
          <div class="theme-swatch-wrapper">
            <div class="theme-swatch" :style="{ background: th.colors.bg, borderColor: th.colors.border }">
              <div class="theme-primary-dot" :style="{ background: th.colors.primary }" />
            </div>
          </div>
          <span>{{ t(th.labelKey) }}</span>
        </div>
      </div>

      <!-- 3. 界面语言 -->
      <div class="fieldset-gap" />
      <label for="lang-select">{{ t('settings.appearance.language') }}</label>
      <AppSelect
        id="lang-select"
        :modelValue="props.selectedLocale"
        :options="props.localeOptions"
        optionLabel="label"
        optionValue="value"
        class="fi lang-select"
        style="width:200px"
        @update:modelValue="handleLocaleChange"
      />
    </div>
  </div>
</template>

<style scoped>
@import '@/views/settings/shared.css';
.field-error { color: var(--danger); font-size: var(--font-size-11); }
/* 修复浅色主题下选项文字对比度不足的问题 */
.theme-option span {
  color: var(--text) !important;
  transition: color 0.2s ease;
}
</style>
