<script setup lang="ts">
import { computed, inject } from 'vue'
import Select from 'primevue/select'
import { THEMES } from '@/config/themes'
import { useAppStore } from '@/stores/app'

defineOptions({ name: 'SettingsTabUI' })

const store = useAppStore()
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!

// 主题列表
const themeList = computed(() => Object.values(THEMES))

const props = defineProps<{
  selectedLocale: string
  localeOptions: { label: string; value: string }[]
  onUploadBg: (e: Event) => void
}>()

const emit = defineEmits<{
  (e: 'update:selectedLocale', val: string): void
  (e: 'localeChange'): void
}>()

function setTheme(v: string) { store.theme = v }

/** 语言切换：先同步值到父组件，再触发 i18n/store 更新 */
function handleLocaleChange(val: string) {
  emit('update:selectedLocale', val)
  emit('localeChange')
}
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">界面设置</div>
    <div class="form-grid">
      <label>登录页背景图</label>
      <div style="display:flex;gap:8px">
        <input :value="getp('appearance.login_bg')" @input="setp('appearance.login_bg',($event.target as any).value)" class="fi" style="flex:1" placeholder="https://... 或留空使用默认" />
        <label class="upload-btn">
          <i class="pi pi-upload" /> 上传
          <input type="file" accept="image/*" style="display:none" @change="props.onUploadBg" />
        </label>
      </div>
      <span></span><span class="text-dim" style="font-size:11px">支持手动上传图片或填入 API 网络地址</span>
      <label>定时公告自动检查</label>
      <select :value="getp('tasks.auto_announce_enabled',false)" @change="setp('tasks.auto_announce_enabled',($event.target as any).value==='true')" class="fi">
        <option :value="false">禁用</option><option :value="true">启用</option>
      </select>
      <label>公告检查 cron</label><input :value="getp('tasks.auto_announce_cron','0 1 * * *')" @input="setp('tasks.auto_announce_cron',($event.target as any).value)" class="fi" />
      <!-- 主题切换（四套主题） -->
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
      <!-- 界面语言选择 -->
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
@import './shared.css';
</style>
