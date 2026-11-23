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
import AppConfirmDialog from '@/components/ui/AppConfirmDialog.vue'
import { getSettings, putSettings, getSettingsSchema, uploadFile, getSettingsMetadata } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import type { TabMeta } from '@/api/settings'
import { useAppStore } from '@/stores/app'
import { THEMES } from '@/config/themes'
import type { ThemeId } from '@/stores/app'
import { usePreferencesStore } from '@/stores/preferences'
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
const isAdmin = computed(() => store.role === 'admin')

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
    const [settings, schema] = await Promise.all([getSettings('/settings'), getSettingsSchema('/settings')])
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
  catch (e) { cfgErr.value = getApiErrorMessage(e) }
}

async function saveCfg() {
  try {
    await putSettings(cfg.value)
    saved.value = true; cfgErr.value = ''
    setTimeout(() => saved.value = false, 2000)
  } catch (e) {
    saved.value = false; cfgErr.value = getApiErrorMessage(e)
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
// 语言名走 i18n（三语值目前都是该语言的自称；将来要改成 "Chinese (Simplified)" 只改 en 一处）
const localeOptions = computed(() => [
  { label: t('settings.locale.zh_cn'), value: 'zh-CN' },
  { label: t('settings.locale.zh_tw'), value: 'zh-TW' },
  { label: 'English', value: 'en' },
])

// 主题下拉的选项：label 沿用原 <option> 的 i18n 表达式 t(cfg.labelKey)，value 为主题 key。
// 这里只做「原生 option 列表 → AppSelect 的 {label,value} 数组」形态转换，
// 文案来源与顺序不变（AppSelect 用 optionLabel/optionValue 取值，不渲染 slot）。
const themeOptions = computed(() =>
  (Object.keys(THEMES) as ThemeId[]).map(key => ({ label: t(THEMES[key].labelKey), value: key })),
)

// ═══════════════════════════════════════════
// 标签页导航
// ═══════════════════════════════════════════
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
import { SETTINGS_TAB_KEYS } from './settings/constants'
import AppButton from '@/components/ui/AppButton.vue'
import AppSelect from '@/components/ui/AppSelect.vue'

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

// ═══════════════════════════════════════════════════════════
// v3.0: scope 分级 — Tab 可见性过滤 + 写操作禁用
// ═══════════════════════════════════════════════════════════
const tabMeta = ref<TabMeta[]>([])
const tabMetaErr = ref(false)

async function loadTabMeta() {
  try {
    const r = await getSettingsMetadata('/settings')
    tabMeta.value = r.tabs
    tabMetaErr.value = false
  } catch { tabMetaErr.value = true }
}

const allowedTabs = computed(() => {
  if (tabMeta.value.length === 0) {
    // fallback: API 不可用时显示全部 Tab（避免空白页）
    return tabs
  }
  const userRole = store.role
  return tabMeta.value
    .filter(t => {
      if (t.scope === 'user') return true
      if (t.scope === 'system-read') return userRole === 'admin'
      if (t.scope === 'system-admin') return userRole === 'admin'
      return false
    })
    .sort((a, b) => a.order - b.order)
    .map(t => ({ key: t.key, label: TAB_LABEL_MAP[t.key] || t.label }))
})

// 当前激活 Tab 的 scope 和写权限
const currentTabScope = computed(() => {
  const meta = tabMeta.value.find(t => t.key === activeTab.value)
  return meta?.scope || 'system-admin'
})

const currentTabCanWrite = computed(() => {
  if (currentTabScope.value === 'user') return true
  if (currentTabScope.value === 'system-admin' && store.role === 'admin') return true
  return false
})

// v3.0: 向子组件注入写权限标志
provide('settingsCanWrite', currentTabCanWrite)

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
    const base = { canWrite: currentTabCanWrite.value }
    // Schema 驱动的 Tab：传递 tabKey（组件 prop 标识符，非 i18n 翻译键）
    if (['storage', 'network', 'query', 'scan', 'ocr', 'tasks'].includes(key)) {
      return { ...base, tabKey: key }
    }
    switch (key) {
      case 'ui':
        // localeOptions 是 computed ref，v-bind 不会深解包：必须取 .value，
        // 否则 PrimeVue Select 拿到 Ref 后 `visibleOptions.findIndex` 报错，整个界面 Tab 渲染中断
        // （2026-07-01 87b36f0b 改成 v-bind="tabProps" 时漏解包，2026-11-20 修）。
        return { ...base, selectedLocale: selectedLocale.value, localeOptions: localeOptions.value, onUploadBg: uploadBg }
      case 'system':
        return { ...base, sections: systemSections.value }
      default:
        return base
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
    cfgErr.value = e.response?.data?.detail || t('common.save_failed')
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
  prefsStore.set('system_sections', val).catch((e) => console.warn('保存系统区块偏好失败，沿用默认分组', e)) // i18n-allow: 开发者日志：偏好保存失败不影响当前界面
}, { deep: true })

// ═══════════════════════════════════════════
// 生命周期
// ═══════════════════════════════════════════
onMounted(() => {
  // 普通用户不请求 /api/settings（admin-only），只保留主题/语言两项本地设置
  if (!isAdmin.value) return
  loadCfg(); loadSystemSections(); loadTabMeta()
})
</script>

<template>
  <AppConfirmDialog />
  <template v-if="isAdmin">
  <h1>{{ t('settings.title') }}</h1>

  <!-- 标签页导航栏 -->
  <div class="tab-bar mt-2">
    <AppButton
      v-for="t in allowedTabs"
      :key="t.key"
      :data-tab="t.key"
      :class="{ active: activeTab === t.key }"
      @click="activeTab = t.key"
  size="s"
  type="ghost"
  bare
>{{ t.label }}</AppButton>
  </div>


  <!-- Tab: dynamic component -->
  <KeepAlive>
    <component :is="currentTabComponent" :ref="setComponentRef" v-bind="tabProps" @update:sections="(val: { cacheManager: boolean; taskManager: boolean }) => systemSections = val" />
  </KeepAlive>

  <!-- 底部操作栏 -->
  <div class="settings-footer">
    <div class="footer-actions">
<AppButton
        :label="t('settings.apply')"
        icon="pi pi-refresh"
        @click="applyCurrentTab"
        :loading="applyLoading"
        :title="t('settings.apply_hint')"
        size="m"
        type="secondary"
      />
<AppButton
        :label="t('settings.ok')"
        icon="pi pi-check"
        @click="saveCfg"
        :title="t('settings.ok_hint')"
        size="m"
        type="secondary"
      />
    </div>
    <div style="display:flex;align-items:center;gap:var(--space-8)">
      <Tag v-if="saved" :value="t('common.saved')" severity="success" />
      <span v-if="cfgErr" class="err-msg">{{ cfgErr }}</span>
      <span class="text-dim" style="font-size:var(--font-size-11)">PilotStd v{{ cfg.version || '—' }}</span>
    </div>
  </div>
</template>

<template v-else>
  <h1>{{ t('settings.title') }}</h1>
  <div class="user-settings">
    <p class="text-dim">{{ t('settings.admin_only') }}</p>
    <label class="row">
      <span>{{ t('settings.theme') }}</span>
      <AppSelect v-model="store.theme" :options="themeOptions" option-label="label" option-value="value" size="m" />
    </label>
    <label class="row">
      <span>{{ t('settings.locale') }}</span>
      <AppSelect v-model="store.locale" :options="localeOptions" option-label="label" option-value="value" size="m" />
    </label>
  </div>
</template>
</template>

<style scoped>
.user-settings { max-width: 520px; margin-top: var(--space-16); display: flex; flex-direction: column; gap: var(--space-16); }
.row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-16); }
/* 下拉框视觉由 <AppSelect size="m"> 承担；这里只给布局宽度（ui-system.md §11.4） */
.row :deep(.app-select) { min-width: 180px; }
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
  padding: var(--space-4);
}
.tab-bar button {
  padding: var(--space-10) var(--space-18);
  border: none;
  background: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: var(--font-size-13);
  font-weight: var(--font-weight-medium);
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
  color: var(--text-on-primary);
  font-weight: var(--font-weight-semibold);
  /* TODO: [Design Debt] 0 2px 8px rgba(99, 102, 241, 0.25) 无精确令牌，暂不替换，待定令牌后统一处理 */
  /* TODO: [Design Debt] 原生阴影与既有 --shadow-* 层级不匹配（半径/扩散/透明度不同），待统一评估（A-52） */
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
}

/* ── 底部操作栏 ── */
.settings-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-20) var(--space-24);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-top: var(--space-24);
  box-shadow: var(--shadow-sm);
}
.footer-actions {
  display: flex;
  gap: var(--space-12);
  align-items: center;
}

/* ── 工具类（父组件专用）── */
.mt-2 { margin-top: var(--space-8); }
.err-msg { color: var(--danger, #e74c3c); font-size: var(--font-size-12); margin-left: var(--space-8); }
.text-dim { color: var(--text-dim); font-size: var(--font-size-13); }
</style>
