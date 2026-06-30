<script setup lang="ts">
import { inject, type Ref } from 'vue'
defineOptions({ name: 'SettingsTabStorage' })
// 从父组件注入共享的配置操作方法
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">存储设置</div>
    <div class="form-grid">
      <label>标准库根目录</label>
      <input :value="getp('storage.root_dir')" @input="setp('storage.root_dir',($event.target as any).value)" class="fi" placeholder="~/标准" />
      <label>过期文件夹名</label>
      <input :value="getp('storage.expire_folder','过期作废')" @input="setp('storage.expire_folder',($event.target as any).value)" class="fi" />
      <label>下载目录</label>
      <input :value="getp('storage.downloads_dir')" @input="setp('storage.downloads_dir',($event.target as any).value)" class="fi" placeholder="默认同标准库" />
      <label>归档后清理源文件</label>
      <select :value="getp('organize.auto_clean_source',false)" @change="setp('organize.auto_clean_source',($event.target as any).value==='true')" class="fi">
        <option :value="false">否</option><option :value="true">是</option>
      </select>
      <label>自动清理只读属性</label>
      <select :value="getp('file.clear_readonly',true)" @change="setp('file.clear_readonly',($event.target as any).value==='true')" class="fi">
        <option :value="true">是</option><option :value="false">否</option>
      </select>
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
