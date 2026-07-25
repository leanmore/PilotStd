<script setup lang="ts">
/**
 * SettingsView — 设置页面（编排层）
 *
 * 职责：标签页导航、共享配置状态管理、底部操作栏。
 * 各 Tab 的内容已拆分为独立子组件（web/src/views/settings/）。
 */
import { ref, onMounted, watch, provide, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import { getSettings, putSettings, getSettingsSchema, uploadFile } from '@/api'
import { useAppStore } from '@/stores/app'
import { usePreferencesStore } from '@/stores/preferences'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

// ── Tab 子组件（Schema 驱动 + 特殊混合布局）──
import SettingsTabSchema from '@/components/SettingsTabSchema.vue'
import SettingsTabAppearanceMixed from '@/components/SettingsTabAppearanceMixed.vue'
// 非 Schema Tab（独立 API）
import SettingsTabSites from './settings/SettingsTabSites.vue'
import SettingsTabUsers from './settings/SettingsTabUsers.vue'
import SettingsTabToken from './settings/SettingsTabToken.vue'
import SettingsTabNotification from './settings/SettingsTabNotification.vue'
import SettingsTabValidity from './settings/SettingsTabValidity.vue'
import SettingsTabSystem from './settings/SettingsTabSystem.vue'
import SettingsTabSchedule from './settings/SettingsTabSchedule.vue'

import 'primeicons/primeicons.css'

defineOptions({ name: 'SettingsView' })

const store = useAppStore()

// ═══════════════════════════════════════════
// 共享配置状态（通过 provide 传递给子 Tab 组件）
// ═══════════════════════════════════════════
const cfg = ref<Record<string, any>>({})
const saved = ref(false)
const cfgErr = ref('')
// Schema 映射表：key → SchemaField + tabs 分组，供 DynamicSettingField 注入
const schemaMap = ref<Record<string, any>>({})
const schemaTabs = ref<Record<string, any[]>>({})

/** 按点号路径读取嵌套配置值 */
/** 按点号路径读取嵌套配置值 */
function getp(path: string, def: any = ''): any {
  const parts = path.split('.')
  let v: any = cfg.value
  for (const p of parts) { if (!v) return def; v = v[p] }
  return v ?? def
}

/** 按点号路径写入嵌套配置值（会就地修改 cfg.value） */
function setp(path: string, val: any) {
  const parts = path.split('.')
  let o: any = cfg.value
  for (let i = 0; i < parts.length - 1; i++) {
    if (!o[parts[i]]) o[parts[i]] = {}
    o = o[parts[i]]
  }
  o[parts[parts.length - 1]] = val
}

async function loadCfg() {
  try {
    const [settings, schema] = await Promise.all([getSettings(), getSettingsSchema()])
    cfg.value = settings; cfgErr.value = ''
    // 构建 key → field 映射表 + tabs 分组
    const map: Record<string, any> = {}
    const tabs: Record<string, any[]> = {}
    for (const [tabName, fields] of Object.entries(schema.tabs)) {
      tabs[tabName] = fields as any[]
      for (const f of fields as any[]) { map[f.key] = f }
    }
    schemaMap.value = map
    schemaTabs.value = tabs
  }
  catch { cfgErr.value = '加载设置失败' }
}

async function saveCfg() {
  try {
    await putSettings(cfg.value)
    saved.value = true; cfgErr.value = ''
    setTimeout(() => saved.value = false, 2000)
  } catch {
    saved.value = false; cfgErr.value = '保存设置失败，请重试'
  }
}

// 提供给子组件注入
provide('settingsGetp', getp)
provide('settingsSetp', setp)
provide('settingsSchema', schemaMap)
provide('settingsSchemaTabs', schemaTabs)
provide('settingsConfig', cfg)

// ═══════════════════════════════════════════
// 上传背景图（UI Tab 回调）
// ═══════════════════════════════════════════
async function uploadBg(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const r = await uploadFile(file)
    setp('appearance.login_bg', r.url)
  } catch (err: any) { /* 上传失败静默处理 */ }
}

// ═══════════════════════════════════════════
// 主题 / 语言（UI Tab 使用）
// ═══════════════════════════════════════════

const selectedLocale = ref(store.locale || 'zh-CN')
const localeOptions = [
  { label: '简体中文', value: 'zh-CN' },
  { label: '繁體中文', value: 'zh-TW' },
  { label: 'English', value: 'en' },
]

// ═══════════════════════════════════════════
// 站点列表（Sites Tab 使用）
// ═══════════════════════════════════════════
const sites = [
  { name: 'ahbz', label: '安徽标准平台', url: 'bzxx.ahbz.org.cn', priority: 1, maxRequests: 200, dailyLimit: 800 },
  { name: 'std_gov', label: '国家标准公开', url: 'openstd.samr.gov.cn', priority: 2, maxRequests: 200, dailyLimit: 800 },
  { name: 'hbba', label: '行业标准平台', url: 'hbba.sacinfo.org.cn', priority: 3, maxRequests: 200, dailyLimit: 800 },
  { name: 'iso_gov', label: '国际标准平台', url: 'std.samr.gov.cn', priority: 4, maxRequests: 200, dailyLimit: 800 },
  { name: 'njbz365', label: '南京标准网', url: 'www.njbz365.cn', priority: 5, maxRequests: 200, dailyLimit: 800 },
  { name: 'dbba', label: '地方标准平台', url: 'dbba.sacinfo.org.cn', priority: 6, maxRequests: 200, dailyLimit: 800 },
  { name: 'csres', label: '工标网', url: 'www.csres.com', priority: 7, maxRequests: 50, dailyLimit: 200 },
]

// ═══════════════════════════════════════════
// 标签页导航
// ═══════════════════════════════════════════
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
import { SETTINGS_TAB_KEYS } from './settings/constants'

const activeTab = ref((route.query.tab as string) || 'storage')

const TAB_LABEL_MAP: Record<string, string> = {
  storage: t('settings.tabs.storage'),
  network: t('settings.tabs.network'),
  query: t('settings.tabs.query'),
  scan: t('settings.tabs.scan'),
  tasks: t('settings.tabs.tasks'),
  ui: t('settings.tabs.ui'),
  ocr: t('settings.tabs.ocr'),
  sites: t('settings.tabs.sites'),
  users: t('settings.tabs.users'),
  token: t('settings.tabs.token'),
  notification: t('settings.tabs.notification'),
  validity: t('settings.tabs.validity'),
  system: t('settings.tabs.system'),
}

const tabs = SETTINGS_TAB_KEYS.map(key => ({ key, label: TAB_LABEL_MAP[key] }))

  // Schema 驱动 Tab → 通用 SettingsTabSchema 组件
  // 非 Schema Tab → 各自独立组件
  const tabComponentMap: Record<string, any> = {
    storage: SettingsTabSchema,
    network: SettingsTabSchema,
    query: SettingsTabSchema,
    scan: SettingsTabSchema,
    tasks: SettingsTabSchedule,
    ocr: SettingsTabSchema,
    ui: SettingsTabAppearanceMixed,
    sites: SettingsTabSites,
    users: SettingsTabUsers,
    token: SettingsTabToken,
    notification: SettingsTabNotification,
    validity: SettingsTabValidity,
    system: SettingsTabSystem,
  }
  const currentTabComponent = computed(() => tabComponentMap[activeTab.value] || null)

  // Schema Tab 通用 props（tabKey） + 界面 Tab 特殊 props
  const tabProps = computed(() => {
    const key = activeTab.value
    // Schema 驱动的 Tab：传递 tabKey
    if (['storage', 'network', 'query', 'scan', 'ocr', 'tasks'].includes(key)) {
      return { tabKey: key }
    }
    switch (key) {
      case 'ui':
        return { selectedLocale: selectedLocale.value, localeOptions, onUploadBg: uploadBg }
      case 'sites':
        return { sites }
      case 'system':
        return { sections: systemSections.value }
      default:
        return {}
    }
  })

watch(activeTab, (newTab) => {
  router.replace({ query: { ...route.query, tab: newTab } })
})

// ═══════════════════════════════════════════
// 底部操作栏："应用"按钮
// ═══════════════════════════════════════════
const applyLoading = ref(false)

// 子组件引用（供"应用"按钮触发独立 API Tab 的保存）
	const dynamicRef = ref<any>(null)
	function setComponentRef(el: any) {
	  dynamicRef.value = el
	}

function extractTabConfig(tabKey: string): Record<string, any> {
  // 从 Schema 中获取该 Tab 的所有配置键的顶层分组
  const fields = schemaTabs.value[tabKey]
  if (!fields || fields.length === 0) return {}
  const categories = new Set(fields.map((f: any) => f.key.split('.')[0]))
  const result: Record<string, any> = {}
  for (const cat of categories) {
    if (cfg.value[cat] !== undefined) result[cat] = cfg.value[cat]
  }
  return result
}

async function applyCurrentTab() {
  const tabKey = activeTab.value
  // 用户和令牌 Tab 无待保存表单，点击无操作
  if (tabKey === 'users' || tabKey === 'token') {
    applyLoading.value = true
    setTimeout(() => applyLoading.value = false, 300)
    return
  }
  applyLoading.value = true
  try {
    switch (tabKey) {
      case 'notification':
        await dynamicRef.value?.saveConfig()
        break
      case 'validity':
        await dynamicRef.value?.doSave()
        await dynamicRef.value?.saveCircuitConfig()
        break
      default: {
        const payload = extractTabConfig(tabKey)
        if (Object.keys(payload).length > 0) {
          await putSettings(payload)
        }
        saved.value = true
        cfgErr.value = ''
        setTimeout(() => saved.value = false, 2000)
        break
      }
    }
  } catch (e: any) {
    cfgErr.value = e.response?.data?.detail || '保存失败'
  } finally {
    applyLoading.value = false
  }
}

// ═══════════════════════════════════════════
// 系统 Tab 折叠状态（持久化到用户首选项）
// ═══════════════════════════════════════════
const DEFAULT_SECTIONS = { cacheManager: true, taskManager: true }
const prefsStore = usePreferencesStore()

const systemSections = ref({ ...DEFAULT_SECTIONS })

// 从后端恢复已保存的折叠状态
async function loadSystemSections() {
  try {
    const all = await prefsStore.getAll()
    const saved = all.system_sections as Record<string, boolean> | undefined
    if (saved) systemSections.value = { ...DEFAULT_SECTIONS, ...saved }
  } catch { /* 未登录或无网络，使用默认值 */ }
}

// 折叠变化时写入后端
watch(systemSections, (val) => {
  prefsStore.set('system_sections', val).catch(() => {})
}, { deep: true })

// ═══════════════════════════════════════════
// 生命周期
// ═══════════════════════════════════════════
onMounted(() => { loadCfg(); loadSystemSections() })
</script>

<template>
  <ConfirmDialog />
  <Toast />
  <h1>设置</h1>

  <!-- 标签页导航栏 -->
  <div class="tab-bar mt-2">
    <button
      v-for="t in tabs"
      :key="t.key"
      :class="{ active: activeTab === t.key }"
      @click="activeTab = t.key"
    >{{ t.label }}</button>
  </div>


  <!-- Tab: dynamic component -->
  <KeepAlive>
    <component :is="currentTabComponent" :ref="setComponentRef" v-bind="tabProps" @update:sections="(val: { cacheManager: boolean; taskManager: boolean }) => systemSections = val" />
  </KeepAlive>

  <!-- 底部操作栏 -->
  <div class="settings-footer">
    <div class="footer-actions">
      <Button
        label="应用"
        icon="pi pi-refresh"
        severity="secondary"
        @click="applyCurrentTab"
        :loading="applyLoading"
        title="仅保存当前 Tab 的设置"
      />
      <Button
        label="确定"
        icon="pi pi-check"
        @click="saveCfg"
        title="保存所有 Tab 的设置"
      />
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <Tag v-if="saved" value="已保存" severity="success" />
      <span v-if="cfgErr" class="err-msg">{{ cfgErr }}</span>
      <span class="text-dim" style="font-size:11px">PilotStd v{{ cfg.version || '—' }}</span>
    </div>
  </div>
</template>

<style scoped>
/* ── 标签页导航 ── */
.tab-bar {
  display: flex;
  gap: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  width: fit-content;
  box-shadow: var(--shadow-xs);
  padding: 4px;
}
.tab-bar button {
  padding: 10px 18px;
  border: none;
  background: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius);
  transition: all var(--transition);
  white-space: nowrap;
  position: relative;
}
.tab-bar button:hover {
  color: var(--text-bright);
  background: var(--selected);
}
.tab-bar button.active {
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  color: #ffffff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
}

/* ── 底部操作栏 ── */
.settings-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-top: 24px;
  box-shadow: var(--shadow-sm);
}
.footer-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* ── 工具类（父组件专用）── */
.mt-2 { margin-top: 8px; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin-left: 8px; }
.text-dim { color: var(--text-dim); font-size: 13px; }
</style>
