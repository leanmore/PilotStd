<script setup lang="ts">
/**
 * SettingsTabAppearanceMixed.vue — 界面设置 Tab（混合布局）。
 *
 * 三部分内容：
 *   1. login_bg 上传区域 — 手写 getp/setp（需要 flex 布局 + 上传按钮）
 *   2. 公告自动检查  — Schema 驱动 DynamicSettingField
 *   3. 主题 / 语言   — Pinia store 管理
 */
import { computed, inject } from 'vue'
import Select from 'primevue/select'
import { THEMES } from '@/config/themes'
import { useAppStore } from '@/stores/app'

defineOptions({ name: 'SettingsTabAppearanceMixed' })

const store = useAppStore()
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!

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

function handleLocaleChange(val: string) {
  emit('update:selectedLocale', val)
  emit('localeChange')
}
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">界面设置</div>
    <div class="form-grid">
      <!-- 1. login_bg 上传区块（手写 getp/setp，flex 布局需要上传按钮） -->
      <label>登录页背景图</label>
      <div style="display:flex;gap:8px">
        <input
          :value="getp('appearance.login_bg')"
          @input="setp('appearance.login_bg', ($event.target as any).value)"
          class="fi" style="flex:1" placeholder="https://... 或留空使用默认"
        />
        <label class="upload-btn">
          <i class="pi pi-upload" /> 上传
          <input type="file" accept="image/*" style="display:none" @change="props.onUploadBg" />
        </label>
      </div>
      <span></span>
      <span class="text-dim" style="font-size:11px">支持手动上传图片或填入 API 网络地址</span>

      <!-- 2. 主题（Pinia store 管理，非 Schema） -->
      <label>主题</label>
      <div class="theme-options">
        <label
          v-for="t in themeList"
          :key="t.id"
          class="theme-option"
          :class="{ active: store.theme === t.id }"
          @click="setTheme(t.id)"
        >
          <div class="theme-swatch-wrapper">
            <div class="theme-swatch" :style="{ background: t.colors.bg, borderColor: t.colors.border }">
              <div class="theme-primary-dot" :style="{ background: t.colors.primary }" />
            </div>
          </div>
          <span>{{ t.label }}</span>
        </label>
      </div>

      <!-- 4. 界面语言（Pinia store 管理，非 Schema） -->
      <label>界面语言</label>
      <Select
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
</style>
