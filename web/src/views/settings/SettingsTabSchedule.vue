<script setup lang="ts">
/**
 * SettingsTabSchedule — 定时任务 Tab
 * 包含定时任务配置（扫描/公告/提醒）+ 文件监控卡片
 */
import { ref, onMounted } from 'vue'
import ToggleSwitch from 'primevue/toggleswitch'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { getSettings, putSettings } from '@/api'
import FileMonitor from '@/components/FileMonitor.vue'

defineOptions({ name: 'SettingsTabSchedule' })

interface TaskConfig {
  auto_scan_enabled: boolean
  auto_scan_cron: string
  auto_announce_enabled: boolean
  auto_announce_cron: string
  date_reminder_enabled: boolean
  date_reminder_cron: string
  auto_health_check_enabled: boolean
  auto_health_check_cron: string
}

const tasks = ref<TaskConfig>({
  auto_scan_enabled: false,
  auto_scan_cron: '0 3 * * *',
  auto_announce_enabled: false,
  auto_announce_cron: '0 1 * * *',
  date_reminder_enabled: false,
  date_reminder_cron: '0 2 * * *',
  auto_health_check_enabled: true,
  auto_health_check_cron: '0 * * * *',
})

const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const errMsg = ref('')
const sections = ref({ tasks: true, fileMonitor: true })

async function loadTasks() {
  loading.value = true; errMsg.value = ''
  try {
    const r = await getSettings()
    if (r.tasks) {
      tasks.value = { ...tasks.value, ...r.tasks }
    }
  } catch {
    errMsg.value = '加载定时任务配置失败'
  } finally {
    loading.value = false
  }
}

async function saveTasks() {
  saving.value = true; saved.value = false; errMsg.value = ''
  try {
    await putSettings({ tasks: { ...tasks.value } })
    saved.value = true
    setTimeout(() => saved.value = false, 2000)
  } catch {
    errMsg.value = '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(loadTasks)
</script>

<template>
  <div class="mt-2">

    <!-- 定时任务配置 -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="sections.tasks = !sections.tasks">
        <span class="collapsible-title">定时任务</span>
        <i :class="sections.tasks ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.tasks" class="collapsible-content">
          <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
          <Message v-if="saved" severity="success" :closable="false">配置已保存</Message>

          <!-- 自动扫描 -->
          <div class="task-row">
            <div class="task-toggle">
              <ToggleSwitch v-model="tasks.auto_scan_enabled" />
              <label>自动扫描标准库</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_scan_enabled">
              <label>Cron 表达式</label>
              <InputText v-model="tasks.auto_scan_cron" placeholder="0 3 * * *" size="small" />
            </div>
          </div>

          <!-- 公告检查 -->
          <div class="task-row">
            <div class="task-toggle">
              <ToggleSwitch v-model="tasks.auto_announce_enabled" />
              <label>公告自动检查</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_announce_enabled">
              <label>Cron 表达式</label>
              <InputText v-model="tasks.auto_announce_cron" placeholder="0 1 * * *" size="small" />
            </div>
          </div>

          <!-- 日期提醒 -->
          <div class="task-row">
            <div class="task-toggle">
              <ToggleSwitch v-model="tasks.date_reminder_enabled" />
              <label>实施日期到期提醒</label>
            </div>
            <div class="task-cron" v-if="tasks.date_reminder_enabled">
              <label>Cron 表达式</label>
              <InputText v-model="tasks.date_reminder_cron" placeholder="0 2 * * *" size="small" />
            </div>
          </div>

          <!-- 适配器健康检查 -->
          <div class="task-row">
            <div class="task-toggle">
              <ToggleSwitch v-model="tasks.auto_health_check_enabled" />
              <label>适配器健康检查</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_health_check_enabled">
              <label>Cron 表达式</label>
              <InputText v-model="tasks.auto_health_check_cron" placeholder="0 * * * *" size="small" />
            </div>
          </div>

          <div class="actions-row">
            <Button label="保存配置" icon="pi pi-check" size="small" :loading="saving" @click="saveTasks" />
          </div>
        </div>
      </transition>
    </div>

    <!-- 文件监控（Q18: 从系统Tab迁移） -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="sections.fileMonitor = !sections.fileMonitor">
        <span class="collapsible-title">文件监控</span>
        <i :class="sections.fileMonitor ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.fileMonitor" class="collapsible-content">
          <FileMonitor />
        </div>
      </transition>
    </div>

  </div>
</template>

<style scoped>
@import './shared.css';

.task-row {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light, #e5e7eb);
}
.task-row:last-of-type {
  border-bottom: none;
}
.task-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 180px;
}
.task-toggle label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.task-cron {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-cron label {
  font-size: 11px;
  color: var(--text-dim);
  white-space: nowrap;
}
.actions-row {
  margin-top: 12px;
}
</style>
