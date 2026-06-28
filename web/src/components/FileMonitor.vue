<script lang="ts">
import { defineComponent, ref, onMounted, onBeforeUnmount } from 'vue'
import http from '@/api/http'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import Tag from 'primevue/tag'
import Message from 'primevue/message'

interface MonitorConfig {
  enabled: boolean
  watch_path: string
  delay_seconds: number
  recursive: boolean
  file_patterns: string[]
  ignore_patterns: string[]
  auto_archive: boolean
}

interface MonitorStatus {
  running: boolean
  enabled: boolean
  watch_path: string
  delay_seconds: number
  last_processed: string
  processed_today: number
  success_today: number
  failed_today: number
}

export default defineComponent({
  name: 'FileMonitor',
  setup() {
    console.log('🚀 FileMonitor setup 执行了');
    const config = ref<MonitorConfig>({
      enabled: true, watch_path: '/inbox', delay_seconds: 5,
      recursive: true, file_patterns: ['.pdf', '.docx', '.doc'],
      ignore_patterns: ['~$', '.tmp', '.swp'], auto_archive: true,
    })

    const status = ref<MonitorStatus>({
      running: false, enabled: true, watch_path: '/inbox',
      delay_seconds: 5, last_processed: '',
      processed_today: 0, success_today: 0, failed_today: 0,
    })

    const saving = ref(false)
    const saved = ref(false)
    const errMsg = ref('')
    const startLoading = ref(false)
    const stopLoading = ref(false)
    let pollTimer: ReturnType<typeof setInterval> | null = null

    async function loadConfig() {
      try {
        const r = await http.get('/monitor/config')
        config.value = {
          enabled: r.data.enabled, watch_path: r.data.watch_path,
          delay_seconds: r.data.delay_seconds, recursive: r.data.recursive,
          file_patterns: Array.isArray(r.data.file_patterns) ? r.data.file_patterns : [],
          ignore_patterns: Array.isArray(r.data.ignore_patterns) ? r.data.ignore_patterns : [],
          auto_archive: r.data.auto_archive,
        }
      } catch { /* ignore */ }
    }

    async function loadStatus() {
      try {
        const r = await http.get('/monitor/status')
        status.value = r.data
      } catch { /* ignore */ }
    }

    async function saveConfig() {
      saving.value = true; saved.value = false
      try {
        await http.put('/monitor/config', {
          ...config.value,
          file_patterns: config.value.file_patterns,
          ignore_patterns: config.value.ignore_patterns,
        })
        saved.value = true
        setTimeout(() => saved.value = false, 2000)
      } catch (e: any) { errMsg.value = e.message } finally { saving.value = false }
    }

    async function startMonitor() {
      startLoading.value = true
      try { await http.post('/monitor/start'); await loadStatus() }
      catch { /* ignore */ } finally { startLoading.value = false }
    }

    async function stopMonitor() {
      stopLoading.value = true
      try { await http.post('/monitor/stop'); await loadStatus() }
      catch { /* ignore */ } finally { stopLoading.value = false }
    }

    onMounted(() => { loadConfig(); loadStatus(); pollTimer = setInterval(loadStatus, 5000) })
    onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })

    return {
      config,
      status,
      saving,
      saved,
      errMsg,
      startLoading,
      stopLoading,
      saveConfig,
      startMonitor,
      stopMonitor,
    }
  },
})
</script>

<template>
  <div>
    <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
    <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>

    <!-- 状态栏 -->
    <div class="monitor-status-bar">
      <div class="status-item">
        <span class="status-label">监控状态</span>
        <Tag :severity="status.running ? 'success' : 'secondary'"
             :value="status.running ? '运行中' : '已停止'" />
      </div>
      <div class="status-item">
        <span class="status-label">监控路径</span>
        <code>{{ status.watch_path }}</code>
      </div>
      <div class="status-item">
        <span class="status-label">今日处理</span>
        <span>{{ status.processed_today }} (成功 {{ status.success_today }} / 失败 {{ status.failed_today }})</span>
      </div>
      <div class="status-item" v-if="status.last_processed">
        <span class="status-label">最近处理</span>
        <span style="font-size:11px">{{ status.last_processed.split('|')[1] || '' }}</span>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-left:auto">
        <Button label="启动" size="small" severity="success" :loading="startLoading" @click="startMonitor" :disabled="status.running" />
        <Button label="停止" size="small" severity="danger" :loading="stopLoading" @click="stopMonitor" :disabled="!status.running" />
      </div>
    </div>

    <!-- 配置 -->
    <div class="monitor-config">
      <div class="field">
        <div style="display:flex;align-items:center;gap:8px">
          <ToggleSwitch v-model="config.enabled" />
          <label>启用文件监控</label>
        </div>
      </div>
      <div class="field-row">
        <div class="field" style="flex:1">
          <label>监控路径</label>
          <InputText v-model="config.watch_path" placeholder="/inbox" />
        </div>
        <div class="field" style="width:140px">
          <label>延迟（秒）</label>
          <InputNumber v-model="config.delay_seconds" :min="1" :max="60" style="width:100%" />
        </div>
      </div>
      <div class="field-row" style="align-items:center">
        <div style="display:flex;align-items:center;gap:8px">
          <ToggleSwitch v-model="config.recursive" />
          <label>监控子目录</label>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <ToggleSwitch v-model="config.auto_archive" />
          <label>自动归档</label>
        </div>
      </div>
      <div class="field">
        <label>文件类型（逗号分隔）</label>
        <InputText :model-value="config.file_patterns.join(',')"
                   @update:model-value="v => config.file_patterns = (v as string).split(',').map(s => s.trim()).filter(Boolean)"
                   placeholder=".pdf,.docx,.doc" />
      </div>
      <div class="field">
        <label>忽略模式（逗号分隔）</label>
        <InputText :model-value="config.ignore_patterns.join(',')"
                   @update:model-value="v => config.ignore_patterns = (v as string).split(',').map(s => s.trim()).filter(Boolean)"
                   placeholder="~$,.tmp,.swp" />
      </div>
      <div style="margin-top:12px">
        <Button label="保存配置" icon="pi pi-check" size="small" :loading="saving" @click="saveConfig" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor-status-bar { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; padding: 12px 16px; background: var(--surface-raised); border-radius: var(--radius); border: 1px solid var(--border); margin-bottom: 16px; }
.status-item { display: flex; flex-direction: column; gap: 4px; }
.status-label { font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.03em; }
.status-item code { font-size: 12px; background: var(--surface); padding: 1px 6px; border-radius: 3px; }
.monitor-config { border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--text-dim); margin-bottom: 4px; }
.field-row { display: flex; gap: 12px; margin-bottom: 10px; align-items: flex-end; }
</style>
