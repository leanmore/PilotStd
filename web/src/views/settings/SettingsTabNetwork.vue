<script setup lang="ts">
import { inject } from 'vue'
defineOptions({ name: 'SettingsTabNetwork' })
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">网络设置</div>
    <div class="form-grid">
      <label>代理地址</label>
      <input :value="getp('network.proxy')" @input="setp('network.proxy',($event.target as any).value)" class="fi" placeholder="http://127.0.0.1:8080" />
      <label>UA 轮转</label>
      <select :value="getp('network.ua_rotation',true)" @change="setp('network.ua_rotation',($event.target as any).value==='true')" class="fi">
        <option :value="true">启用</option><option :value="false">禁用</option>
      </select>
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
