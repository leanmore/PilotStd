<script setup lang="ts">
import { inject } from 'vue'
defineOptions({ name: 'SettingsTabScan' })
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!
const arrstr = inject<(v: any) => string>('settingsArrstr')!
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">扫描设置</div>
    <div class="form-grid">
      <label>跳过文件夹</label>
      <input :value="arrstr(getp('scan.skip_folders',['过期作废']))" @input="setp('scan.skip_folders',($event.target as any).value.split(',').map((s:string)=>s.trim()).filter(Boolean))" class="fi" placeholder="过期作废" />
      <label>文件扩展名</label>
      <input :value="arrstr(getp('scan.extensions',['.pdf','.doc','.docx','.txt']))" @input="setp('scan.extensions',($event.target as any).value.split(',').map((s:string)=>s.trim()).filter(Boolean))" class="fi" placeholder=".pdf, .doc, .docx" />
      <label>跳过文件关键词</label>
      <input :value="arrstr(getp('scan.skip_file_keywords',[]))" @input="setp('scan.skip_file_keywords',($event.target as any).value.split(',').map((s:string)=>s.trim()).filter(Boolean))" class="fi" placeholder="~$" />
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
