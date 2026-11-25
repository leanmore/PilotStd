<script setup lang="ts">
/**
 * SettingsTabSchedule — 定时任务 Tab
 * 包含定时任务配置（扫描/公告/提醒）+ 文件监控卡片
 * 文案全部走 i18n（settings.tabs.tasks / settings.tasks.* / settings.file_monitor.*），不硬编码中文
 */
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Message from 'primevue/message'
import { getSettings, putSettings } from '@/api'
import FileMonitor from '@/components/FileMonitor.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppToggle from '@/components/ui/AppToggle.vue'

defineOptions({ name: 'SettingsTabSchedule' })

const { t } = useI18n()

interface TaskConfig {
  auto_scan_enabled: boolean
  auto_scan_cron: string
  auto_announce_enabled: boolean
  auto_announce_cron: string
  date_reminder_enabled: boolean
  date_reminder_cron: string
  auto_health_check_enabled: boolean
  auto_health_check_cron: string
  // 收藏标准下载归档（favorite_chain_processor.process_chain）——2026-09-25 补入，
  // 此前该任务不在设置页，用户无法查看/修改其 cron，也无法手动触发（技术债 #20）
  auto_archive_retry_enabled: boolean
  auto_archive_retry_cron: string
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
  auto_archive_retry_enabled: true,
  auto_archive_retry_cron: '0 4 * * *',
})

const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const errMsg = ref('')
const sections = ref({ tasks: true, fileMonitor: true })

async function loadTasks() {
  loading.value = true; errMsg.value = ''
  try {
    const r = await getSettings('/settings')
    if (r.tasks) {
      tasks.value = { ...tasks.value, ...r.tasks }
    }
  } catch {
    errMsg.value = t('settings.tasks.load_failed')
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
    errMsg.value = t('common.save_failed')
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
        <span class="collapsible-title">{{ t('settings.tabs.tasks') }}</span>
        <i :class="sections.tasks ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="collapsible-icon" />
      </div>
      <transition name="collapsible">
        <div v-show="sections.tasks" class="collapsible-content">
          <Message v-if="errMsg" severity="error" :closable="false">{{ errMsg }}</Message>
          <Message v-if="saved" severity="success" :closable="false">{{ t('settings.saved') }}</Message>

          <!-- 自动扫描 -->
          <div class="task-row">
            <div class="task-toggle">
              <AppToggle v-model="tasks.auto_scan_enabled" />
              <label>{{ t('settings.tasks.scan') }}</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_scan_enabled">
              <label>{{ t('settings.tasks.cron_label') }}</label>
              <AppInput v-model="tasks.auto_scan_cron" placeholder="0 3 * * *" size="s" />
            </div>
          </div>

          <!-- 公告检查 -->
          <div class="task-row">
            <div class="task-toggle">
              <AppToggle v-model="tasks.auto_announce_enabled" />
              <label>{{ t('settings.tasks.announce') }}</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_announce_enabled">
              <label>{{ t('settings.tasks.cron_label') }}</label>
              <AppInput v-model="tasks.auto_announce_cron" placeholder="0 1 * * *" size="s" />
            </div>
          </div>

          <!-- 日期提醒 -->
          <div class="task-row">
            <div class="task-toggle">
              <AppToggle v-model="tasks.date_reminder_enabled" />
              <label>{{ t('settings.tasks.reminder') }}</label>
            </div>
            <div class="task-cron" v-if="tasks.date_reminder_enabled">
              <label>{{ t('settings.tasks.cron_label') }}</label>
              <AppInput v-model="tasks.date_reminder_cron" placeholder="0 2 * * *" size="s" />
            </div>
          </div>

          <!-- 适配器健康检查 -->
          <div class="task-row">
            <div class="task-toggle">
              <AppToggle v-model="tasks.auto_health_check_enabled" />
              <label>{{ t('settings.tasks.health_check') }}</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_health_check_enabled">
              <label>{{ t('settings.tasks.cron_label') }}</label>
              <AppInput v-model="tasks.auto_health_check_cron" placeholder="0 * * * *" size="s" />
            </div>
          </div>

          <!-- 收藏标准下载归档 -->
          <div class="task-row">
            <div class="task-toggle">
              <AppToggle v-model="tasks.auto_archive_retry_enabled" />
              <label>{{ t('settings.tasks.archive_retry') }}</label>
            </div>
            <div class="task-cron" v-if="tasks.auto_archive_retry_enabled">
              <label>{{ t('settings.tasks.cron_label') }}</label>
              <AppInput v-model="tasks.auto_archive_retry_cron" placeholder="0 4 * * *" size="s" />
            </div>
            <div class="task-hint">{{ t('settings.tasks.archive_retry_hint') }}</div>
          </div>

          <div class="actions-row">
<AppButton
              :label="t('settings.save_config')"
              icon="pi pi-check"
              :loading="saving"
              @click="saveTasks"
              size="s"
              type="secondary"
            />
          </div>
        </div>
      </transition>
    </div>

    <!-- 文件监控（Q18: 从系统Tab迁移） -->
    <div class="collapsible-card">
      <div class="collapsible-header" @click="sections.fileMonitor = !sections.fileMonitor">
        <span class="collapsible-title">{{ t('settings.file_monitor.title') }}</span>
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
  flex-wrap: wrap; /* 必须换行：第 5 行的 .task-hint 靠 flex-basis:100% 独占一行；
                      若为 nowrap，该 100% 基准会把同行所有项压到负剩余空间，
                      开关（.p-toggleswitch 无 flex:none 保护）被等比压缩 → 第 5 个开关比前四个窄 */
  align-items: center;
  gap: var(--space-20);
  padding: var(--space-10) 0;
  border-bottom: 1px solid var(--border-light);
}
.task-row:last-of-type {
  border-bottom: none;
}
.task-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  min-width: 180px;
  flex: 0 0 auto; /* 开关组不参与收缩，保证五个开关尺寸完全一致（宽度/高度/左对齐） */
}
.task-toggle label {
  font-size: var(--font-size-13);
  font-weight: var(--font-weight-medium);
  color: var(--text);
}
.task-cron {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}
.task-cron label {
  font-size: var(--font-size-11);
  color: var(--text-secondary);
  white-space: nowrap;
}
.task-hint {
  flex-basis: 100%;
  font-size: var(--font-size-11);
  color: var(--text-secondary);
}
.actions-row {
  margin-top: var(--space-12);
}
</style>
