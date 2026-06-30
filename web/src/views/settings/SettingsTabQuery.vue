<script setup lang="ts">
import { inject } from 'vue'
defineOptions({ name: 'SettingsTabQuery' })
const getp = inject<(path: string, def?: any) => any>('settingsGetp')!
const setp = inject<(path: string, val: any) => void>('settingsSetp')!
</script>

<template>
  <div class="card mt-2">
    <div class="card-header">查询设置</div>
    <div class="form-grid">
      <label>启用缓存</label>
      <select :value="getp('query.use_cache',true)" @change="setp('query.use_cache',($event.target as any).value==='true')" class="fi">
        <option :value="true">是</option><option :value="false">否</option>
      </select>
      <label>查询间隔(秒)</label>
      <input :value="getp('query.interval',0.5)" @input="setp('query.interval',parseFloat(($event.target as any).value)||0)" class="fi" type="number" step="0.1" />
    </div>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
