<script setup lang="ts">
/**
 * SettingsView — 设置页面（编排层）
 *
 * 职责：标签页导航、共享配置状态管理、底部操作栏。
 * 各 Tab 的内容已拆分为独立子组件（web/src/views/settings/）。
 */
import { ref, onMounted, watch, provide } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import { getSettings, putSettings, uploadFile } from '@/api'
import { useAppStore } from '@/stores/app'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

// ── Tab 子组件 ──
import SettingsTabStorage from './settings/SettingsTabStorage.vue'
import SettingsTabNetwork from './settings/SettingsTabNetwork.vue'
import SettingsTabQuery from './settings/SettingsTabQuery.vue'
import SettingsTabScan from './settings/SettingsTabScan.vue'
import SettingsTabUI from './settings/SettingsTabUI.vue'
import SettingsTabOCR from './settings/SettingsTabOCR.vue'
import SettingsTabSites from './settings/SettingsTabSites.vue'
import SettingsTabUsers from './settings/SettingsTabUsers.vue'
import SettingsTabToken from './settings/SettingsTabToken.vue'
import SettingsTabCircuit from './settings/SettingsTabCircuit.vue'
import SettingsTabNotification from './settings/SettingsTabNotification.vue'
import SettingsTabValidity from './settings/SettingsTabValidity.vue'
import SettingsTabSystem from './settings/SettingsTabSystem.vue'

import 'primeicons/primeicons.css'

defineOptions({ name: 'SettingsView' })

const store = useAppStore()
const { locale } = useI18n()

// ═══════════════════════════════════════════
// 共享配置状态（通过 provide 传递给子 Tab 组件）
// ═══════════════════════════════════════════
const cfg = ref<Record<string, any>>({})
const saved = ref(false)
const cfgErr = ref('')

/** 按点号路径读取嵌套配置值 */
function getp(path: string, def: any = ''): any {
  const parts = path.split('.')
  let v: any = cfg.value
  for (const p of parts) { if (!v) return def; v = v[p] }
  return v ?? def
}

/** 将数组转为逗号分隔字符串（用于表单输入框显示） */
function arrstr(v: any): string {
  return Array.isArray(v) ? v.join(', ') : (typeof v === 'string' ? v : '')
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
  try { const r = await getSettings(); cfg.value = r; cfgErr.value = '' }
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
provide('settingsArrstr', arrstr)

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
function setTheme(v: string) { store.theme = v }

const selectedLocale = ref(store.locale || 'zh-CN')
const localeOptions = [
  { label: '简体中文', value: 'zh-CN' },
  { label: '繁體中文', value: 'zh-TW' },
  { label: 'English', value: 'en' },
]
function onLocaleChange() {
  locale.value = selectedLocale.value
  store.locale = selectedLocale.value
}

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
const activeTab = ref((route.query.tab as string) || 'storage')

const tabs = [
  { key: 'storage', label: '存储' },
  { key: 'network', label: '网络' },
  { key: 'query', label: '查询' },
  { key: 'scan', label: '扫描' },
  { key: 'ui', label: '界面' },
  { key: 'ocr', label: 'OCR' },
  { key: 'sites', label: '站点' },
  { key: 'users', label: '用户' },
  { key: 'token', label: 'API 令牌' },
  { key: 'circuit', label: '熔断' },
  { key: 'notification', label: '通知' },
  { key: 'validity', label: '时效性' },
  { key: 'system', label: '系统' },
]

watch(activeTab, (newTab) => {
  router.replace({ query: { ...route.query, tab: newTab } })
})

// ═══════════════════════════════════════════
// 底部操作栏："应用"按钮
// ═══════════════════════════════════════════
const tabConfigKeys: Record<string, string[]> = {
  storage: ['storage', 'organize', 'file'],
  network: ['network'],
  query: ['query'],
  scan: ['scan'],
  ui: ['appearance', 'tasks'],
  ocr: ['ocr'],
  sites: ['sites'],
  system: [],
  circuit: [],
  notification: [],
  validity: [],
  users: [],
  token: [],
}

const applyLoading = ref(false)

// 子组件引用（供"应用"按钮触发独立 API Tab 的保存）
const circuitRef = ref<InstanceType<typeof SettingsTabCircuit> | null>(null)
const notificationRef = ref<InstanceType<typeof SettingsTabNotification> | null>(null)
const validityRef = ref<InstanceType<typeof SettingsTabValidity> | null>(null)

function extractTabConfig(tabKey: string): Record<string, any> {
  const keys = tabConfigKeys[tabKey] || []
  const result: Record<string, any> = {}
  for (const k of keys) {
    if (cfg.value[k] !== undefined) result[k] = cfg.value[k]
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
      case 'circuit':
        await circuitRef.value?.saveCircuitConfig()
        break
      case 'notification':
        await notificationRef.value?.saveConfig()
        break
      case 'validity':
        await validityRef.value?.doSave()
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
// 系统 Tab 折叠状态
// ═══════════════════════════════════════════
const systemSections = ref({
  fileMonitor: true,
  cacheManager: true,
  taskManager: true,
})

// ═══════════════════════════════════════════
// 生命周期
// ═══════════════════════════════════════════
onMounted(() => { loadCfg() })
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

  <!-- Tab: 存储 -->
  <SettingsTabStorage v-show="activeTab === 'storage'" />

  <!-- Tab: 网络 -->
  <SettingsTabNetwork v-show="activeTab === 'network'" />

  <!-- Tab: 查询 -->
  <SettingsTabQuery v-show="activeTab === 'query'" />

  <!-- Tab: 扫描 -->
  <SettingsTabScan v-show="activeTab === 'scan'" />

  <!-- Tab: 界面 -->
  <SettingsTabUI
    v-show="activeTab === 'ui'"
    :selected-locale="selectedLocale"
    :locale-options="localeOptions"
    :on-upload-bg="uploadBg"
    @update:selected-locale="selectedLocale = $event"
    @locale-change="onLocaleChange"
  />

  <!-- Tab: OCR -->
  <SettingsTabOCR v-show="activeTab === 'ocr'" />

  <!-- Tab: 站点 -->
  <SettingsTabSites v-show="activeTab === 'sites'" :sites="sites" />

  <!-- Tab: 用户（自包含，含对话框） -->
  <SettingsTabUsers v-show="activeTab === 'users'" />

  <!-- Tab: API 令牌（自包含，含对话框） -->
  <SettingsTabToken v-show="activeTab === 'token'" />

  <!-- Tab: 熔断（自包含，暴露 saveCircuitConfig） -->
  <SettingsTabCircuit ref="circuitRef" v-show="activeTab === 'circuit'" />

  <!-- Tab: 通知（暴露 saveConfig） -->
  <SettingsTabNotification ref="notificationRef" v-show="activeTab === 'notification'" />

  <!-- Tab: 时效性（暴露 doSave） -->
  <SettingsTabValidity ref="validityRef" v-show="activeTab === 'validity'" />

  <!-- Tab: 系统（三块可折叠区域） -->
  <SettingsTabSystem
    v-show="activeTab === 'system'"
    :sections="systemSections"
    @update:sections="systemSections = $event"
  />

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
