<script setup lang="ts">
import { inject } from 'vue'
defineOptions({ name: 'SettingsTabOCR' })
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">OCR 识别设置</div>
    <p class="text-dim">三云调度（百度云+腾讯云主力，阿里云应急），各平台均有免费额度</p>
    <div class="form-grid">
      <label class="fieldset-label">百度云</label><span></span>
      <label>API Key</label>
      <input :value="getp('ocr.baidu_api_key')" @input="setp('ocr.baidu_api_key',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
      <label>Secret Key</label>
      <input :value="getp('ocr.baidu_secret_key')" @input="setp('ocr.baidu_secret_key',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
      <div class="fieldset-gap"></div>
      <label class="fieldset-label">腾讯云</label><span></span>
      <label>Secret ID</label>
      <input :value="getp('ocr.tencent_secret_id')" @input="setp('ocr.tencent_secret_id',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
      <label>Secret Key</label>
      <input :value="getp('ocr.tencent_secret_key')" @input="setp('ocr.tencent_secret_key',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
      <div class="fieldset-gap"></div>
      <label class="fieldset-label">阿里云（应急）</label><span></span>
      <label>Access Key ID</label>
      <input :value="getp('ocr.aliyun_access_key_id')" @input="setp('ocr.aliyun_access_key_id',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
      <label>Access Key Secret</label>
      <input :value="getp('ocr.aliyun_access_key_secret')" @input="setp('ocr.aliyun_access_key_secret',($event.target as any).value)" class="fi password-mask" type="password" autocomplete="off" />
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
