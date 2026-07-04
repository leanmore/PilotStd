<script setup lang="ts">
import { ref, inject } from 'vue'
defineOptions({ name: 'SettingsTabOCR' })

const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!

// 折叠状态（持久化到 localStorage）
const ocrSections = ref({
  provider: localStorage.getItem('ocr_section_provider') !== 'false',
  advanced: localStorage.getItem('ocr_section_advanced') !== 'false',
})

function toggle(key: 'provider' | 'advanced') {
  ocrSections.value[key] = !ocrSections.value[key]
  localStorage.setItem(`ocr_section_${key}`, String(ocrSections.value[key]))
}
</script>

<template>
  <!-- OCR 提供商 -->
  <div class="collapsible-card mt-2">
    <div class="collapsible-header" @click="toggle('provider')">
      <span class="collapsible-title">OCR 提供商</span>
      <i :class="ocrSections.provider ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="ocrSections.provider" class="collapsible-content">
        <p class="text-dim" style="margin-bottom:12px">三云调度（百度云+腾讯云主力，阿里云应急），各平台均有免费额度</p>
        <div class="form-grid">
          <label class="fieldset-label">百度云</label>
          <label>API Key</label>
          <input :value="getp('ocr.baidu_api_key')" @input="setp('ocr.baidu_api_key',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
          <label>Secret Key</label>
          <input :value="getp('ocr.baidu_secret_key')" @input="setp('ocr.baidu_secret_key',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
          <div class="fieldset-gap"></div>
          <label class="fieldset-label">腾讯云</label>
          <label>Secret ID</label>
          <input :value="getp('ocr.tencent_secret_id')" @input="setp('ocr.tencent_secret_id',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
          <label>Secret Key</label>
          <input :value="getp('ocr.tencent_secret_key')" @input="setp('ocr.tencent_secret_key',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
        </div>
      </div>
    </transition>
  </div>

  <!-- 高级选项 -->
  <div class="collapsible-card">
    <div class="collapsible-header" @click="toggle('advanced')">
      <span class="collapsible-title">高级选项</span>
      <i :class="ocrSections.advanced ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
    </div>
    <transition name="collapsible">
      <div v-show="ocrSections.advanced" class="collapsible-content">
        <div class="form-grid">
          <label class="fieldset-label">阿里云（应急）</label>
          <label>Access Key ID</label>
          <input :value="getp('ocr.aliyun_access_key_id')" @input="setp('ocr.aliyun_access_key_id',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
          <label>Access Key Secret</label>
          <input :value="getp('ocr.aliyun_access_key_secret')" @input="setp('ocr.aliyun_access_key_secret',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
