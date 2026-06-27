<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import { getUsers, addUser, deleteUser, changePassword, getSettings, putSettings, uploadFile, getToken, refreshToken } from '@/api'
import { useAppStore } from '@/stores/app'
import { THEMES } from '@/config/themes'
import http from '@/api/http'
import NotificationConfig from '@/components/NotificationConfig.vue'
import WechatTrustIP from '@/components/WechatTrustIP.vue'
import CacheManager from '@/components/CacheManager.vue'
import FileMonitor from '@/components/FileMonitor.vue'
import TaskManager from '@/components/TaskManager.vue'
import ValidityConfig from '@/components/ValidityConfig.vue'
const store = useAppStore()
const { locale } = useI18n()
const confirm = useConfirm()
const toast = useToast()
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import Card from 'primevue/card'

// 主题列表（供模板使用）
const themeList = computed(() => Object.values(THEMES))

// ── 用户管理 ──
const users = ref<any[]>([]); const showAdd = ref(false)
const newUser = ref({ username: '', password: '', role: 'user' }); const userErr = ref(''); const loadUsersErr = ref('')
async function loadUsers() {
  try { const r = await getUsers(); users.value = r.users; loadUsersErr.value = '' } catch { loadUsersErr.value = '加载用户列表失败' }
}
async function doAdd() {
  // 校验保留用户名
  if (newUser.value.username.toLowerCase() === 'admin') {
    toast.add({ severity: 'error', summary: '用户名不可用', detail: '"admin" 为保留用户名，请使用其他名称', life: 4000 })
    return
  }
  try { await addUser(newUser.value.username, newUser.value.password, newUser.value.role); showAdd.value = false; newUser.value = { username: '', password: '', role: 'user' }; userErr.value = ''; loadUsers() }
  catch (e: any) { userErr.value = e.response?.data?.detail || '失败' }
}
async function doDelete(id: number) { await deleteUser(id); loadUsers() }

// ── 用户管理辅助 ──
const SUPERUSER_USERNAME = 'admin'
const currentUser = computed(() => users.value.find((u: any) => u.username === store.username) || null)

function canDelete(item: any): boolean {
  if (!currentUser.value || currentUser.value.username !== SUPERUSER_USERNAME) return false
  if (item.id === currentUser.value.id) return false
  return true
}

function confirmDelete(item: any) {
  confirm.require({
    message: `确定要删除用户 "${item.username}" 吗？此操作不可恢复。`,
    header: '删除确认',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: '确认删除',
    acceptClass: 'p-button-danger',
    rejectLabel: '取消',
    accept: () => doDelete(item.id),
  })
}

// ── 修改密码 ──
const showPwd = ref(false); const pwdForm = ref({ old: '', new: '', confirm: '' }); const pwdErr = ref('')
async function doChangePwd() {
  pwdErr.value = ''
  if (!pwdForm.value.old || !pwdForm.value.new) { pwdErr.value = '请填写旧密码和新密码'; return }
  if (pwdForm.value.new.length < 4) { pwdErr.value = '新密码至少4个字符'; return }
  if (pwdForm.value.new !== pwdForm.value.confirm) { pwdErr.value = '两次输入的新密码不一致'; return }
  try {
    await changePassword(pwdForm.value.old, pwdForm.value.new)
    showPwd.value = false; pwdForm.value = { old: '', new: '', confirm: '' }
    alert('密码已修改')
  } catch (e: any) { pwdErr.value = e.response?.data?.detail || '修改失败' }
}

// ── 设置 ──
const cfg = ref<Record<string,any>>({}); const saved = ref(false); const cfgErr = ref('')
function getp(path: string, def: any = '') { const parts = path.split('.'); let v: any = cfg.value; for (const p of parts) { if (!v) return def; v = v[p] } return v ?? def }
function arrstr(v: any): string { return Array.isArray(v) ? v.join(', ') : (typeof v === 'string' ? v : '') }
function setp(path: string, val: any) { const parts = path.split('.'); let o: any = cfg.value; for (let i = 0; i < parts.length - 1; i++) { if (!o[parts[i]]) o[parts[i]] = {}; o = o[parts[i]] } o[parts[parts.length - 1]] = val }
async function loadCfg() {
  try { const r = await getSettings(); cfg.value = r; cfgErr.value = '' } catch { cfgErr.value = '加载设置失败' }
}
async function saveCfg() {
  try { await putSettings(cfg.value); saved.value = true; cfgErr.value = ''; setTimeout(() => saved.value = false, 2000) } catch { saved.value = false; cfgErr.value = '保存设置失败，请重试' }
}
async function uploadBg(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const r = await uploadFile(file)
    setp('appearance.login_bg', r.url)
  } catch (err: any) { userErr.value = err.response?.data?.detail || '上传失败' }
}

function setTheme(v: string) { store.theme = v }

// ── 语言选择 ──
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

// ── 熔断配置 ──
interface CircuitConfig {
  failure_threshold: number
  freeze_durations: number[]
  reset_window_hours: number
}
const circuitCfg = ref<CircuitConfig>({ failure_threshold: 3, freeze_durations: [30, 120, 360, 720], reset_window_hours: 24 })
const circuitErr = ref('')
const circuitSaved = ref(false)
const circuitLoading = ref(false)

async function loadCircuitConfig() {
  try {
    const r = await http.get('/adapter/config')
    circuitCfg.value = r.data
    circuitErr.value = ''
  } catch {
    circuitErr.value = '加载配置失败'
  }
}

function validateDurations(): string | null {
  const d = circuitCfg.value.freeze_durations
  for (let i = 0; i < d.length; i++) {
    if (!d[i] || d[i] < 1) return `第${i + 1}阶梯时长必须 >= 1`
    if (i > 0 && d[i] <= d[i - 1]) return '阶梯时长必须严格递增'
  }
  if (circuitCfg.value.failure_threshold < 1) return '失败阈值必须 >= 1'
  if (circuitCfg.value.reset_window_hours < 1) return '归零窗口必须 >= 1'
  return null
}

async function saveCircuitConfig() {
  const err = validateDurations()
  if (err) { circuitErr.value = err; return }
  circuitLoading.value = true
  circuitSaved.value = false
  try {
    await http.put('/adapter/config', circuitCfg.value)
    circuitSaved.value = true
    circuitErr.value = ''
    await loadCircuitConfig()
    setTimeout(() => circuitSaved.value = false, 2000)
  } catch (e: any) {
    circuitErr.value = e.response?.data?.error || '保存配置失败'
  } finally {
    circuitLoading.value = false
  }
}
onMounted(() => { loadUsers(); loadCfg(); loadToken(); loadCircuitConfig() })

// ── API 令牌 ──
const token = ref(''); const tokenErr = ref(''); const tokenLoading = ref(false)
const showToken = ref(false); const tokenCopied = ref(false); const showRefreshDlg = ref(false)
function maskToken(t: string) {
  if (!t || t.length <= 12) return t ? t.slice(0, 8) + '****' : ''
  return t.slice(0, 8) + '****' + t.slice(-4)
}
async function loadToken() {
  try { const r = await getToken(); token.value = r.token; tokenErr.value = '' } catch { tokenErr.value = '加载令牌失败（需要管理员权限）' }
}
async function copyToken() {
  try {
    await navigator.clipboard.writeText(token.value)
    tokenCopied.value = true
  } catch {
    // 降级：HTTP 环境下 clipboard API 不可用，使用 textarea + execCommand
    try {
      const ta = document.createElement('textarea')
      ta.value = token.value
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      tokenCopied.value = true
    } catch { /* 降级也失败，静默忽略 */ }
  }
  if (tokenCopied.value) setTimeout(() => tokenCopied.value = false, 2000)
}
async function doRefreshToken() {
  tokenLoading.value = true; tokenErr.value = ''
  try { const r = await refreshToken(); token.value = r.token; showToken.value = true; showRefreshDlg.value = false; tokenLoading.value = false } catch { tokenErr.value = '刷新失败，请确认管理员权限'; tokenLoading.value = false }
}

// 标签页
const activeTab = ref('storage')
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

// 底部操作栏：每个 Tab 对应的 cfg 顶层键（用于"应用"按钮提取对应字段）
const tabConfigKeys: Record<string, string[]> = {
  'storage':   ['storage', 'organize', 'file'],
  'network':   ['network'],
  'query':     ['query'],
  'scan':      ['scan'],
  'ui':        ['appearance', 'tasks'],
  'ocr':       ['ocr'],
  'sites':     ['sites'],
  'circuit':   [],  // 独立 API — 不走 /settings
  'notification': [],  // 独立 API — 子组件内部保存
  'validity':      [],  // 独立 API — 子组件内部保存
  'users':     [],
  'token':     [],
}

const applyLoading = ref(false)

// 子组件引用（用于"应用"按钮触发子组件内部保存）
const notificationRef = ref<InstanceType<typeof NotificationConfig> | null>(null)
const validityRef = ref<InstanceType<typeof ValidityConfig> | null>(null)

function extractTabConfig(tabKey: string): Record<string, any> {
  const keys = tabConfigKeys[tabKey] || []
  const result: Record<string, any> = {}
  for (const k of keys) {
    if (cfg.value[k] !== undefined) {
      result[k] = cfg.value[k]
    }
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
      // 独立 API 的 Tab
      case 'circuit':
        await saveCircuitConfig()
        break
      case 'notification':
        await notificationRef.value?.saveConfig()
        break
      case 'validity':
        await validityRef.value?.doSave()
        break
      // 通过 /api/settings 部分更新的 Tab
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

// 站点信息（与 pilotstd/query/site_config.py 同步）
const sites = [
  { name: 'ahbz', label: '安徽标准平台', url: 'bzxx.ahbz.org.cn', priority: 1, maxRequests: 200, dailyLimit: 800 },
  { name: 'std_gov', label: '国家标准公开', url: 'openstd.samr.gov.cn', priority: 2, maxRequests: 200, dailyLimit: 800 },
  { name: 'hbba', label: '行业标准平台', url: 'hbba.sacinfo.org.cn', priority: 3, maxRequests: 200, dailyLimit: 800 },
  { name: 'iso_gov', label: '国际标准平台', url: 'std.samr.gov.cn', priority: 4, maxRequests: 200, dailyLimit: 800 },
  { name: 'njbz365', label: '南京标准网', url: 'www.njbz365.cn', priority: 5, maxRequests: 200, dailyLimit: 800 },
  { name: 'dbba', label: '地方标准平台', url: 'dbba.sacinfo.org.cn', priority: 6, maxRequests: 200, dailyLimit: 800 },
  { name: 'csres', label: '工标网', url: 'www.csres.com', priority: 7, maxRequests: 50, dailyLimit: 200 },
]
</script>

<template>
  <ConfirmDialog />
  <Toast />
  <h1>设置</h1>

  <div class="tab-bar mt-2">
    <button v-for="t in tabs" :key="t.key" :class="{ active: activeTab === t.key }" @click="activeTab = t.key">{{ t.label }}</button>
  </div>

  <!-- 存储 -->
  <div v-show="activeTab === 'storage'" class="card mt-2">
    <div class="card-header">存储设置</div>
    <div class="form-grid">
      <label>标准库根目录</label><input :value="getp('storage.root_dir')" @input="setp('storage.root_dir',($event.target as any).value)" class="fi" placeholder="~/标准" />
      <label>过期文件夹名</label><input :value="getp('storage.expire_folder','过期作废')" @input="setp('storage.expire_folder',($event.target as any).value)" class="fi" />
      <label>下载目录</label><input :value="getp('storage.downloads_dir')" @input="setp('storage.downloads_dir',($event.target as any).value)" class="fi" placeholder="默认同标准库" />
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

  <!-- 网络 -->
  <div v-show="activeTab === 'network'" class="card mt-2">
    <div class="card-header">网络设置</div>
    <div class="form-grid">
      <label>代理地址</label><input :value="getp('network.proxy')" @input="setp('network.proxy',($event.target as any).value)" class="fi" placeholder="http://127.0.0.1:8080" />
      <label>UA 轮转</label>
      <select :value="getp('network.ua_rotation',true)" @change="setp('network.ua_rotation',($event.target as any).value==='true')" class="fi">
        <option :value="true">启用</option><option :value="false">禁用</option>
      </select>
    </div>
  </div>

  <!-- 查询 -->
  <div v-show="activeTab === 'query'" class="card mt-2">
    <div class="card-header">查询设置</div>
    <div class="form-grid">
      <label>启用缓存</label>
      <select :value="getp('query.use_cache',true)" @change="setp('query.use_cache',($event.target as any).value==='true')" class="fi">
        <option :value="true">是</option><option :value="false">否</option>
      </select>
      <label>查询间隔(秒)</label><input :value="getp('query.interval',0.5)" @input="setp('query.interval',parseFloat(($event.target as any).value)||0)" class="fi" type="number" step="0.1" />
    </div>
  </div>

  <!-- 扫描 -->
  <div v-show="activeTab === 'scan'" class="card mt-2">
    <div class="card-header">扫描设置</div>
    <div class="form-grid">
      <label>跳过文件夹</label><input :value="arrstr(getp('scan.skip_folders',['过期作废']))" @input="setp('scan.skip_folders',($event.target as any).value.split(',').map((s:string)=>s.trim()).filter(Boolean))" class="fi" placeholder="过期作废" />
      <label>文件扩展名</label><input :value="arrstr(getp('scan.extensions',['.pdf','.doc','.docx','.txt']))" @input="setp('scan.extensions',($event.target as any).value.split(',').map((s:string)=>s.trim()).filter(Boolean))" class="fi" placeholder=".pdf, .doc, .docx" />
      <label>跳过文件关键词</label><input :value="arrstr(getp('scan.skip_file_keywords',[]))" @input="setp('scan.skip_file_keywords',($event.target as any).value.split(',').map((s:string)=>s.trim()).filter(Boolean))" class="fi" placeholder="~$" />
    </div>
  </div>

  <!-- 界面 -->
  <div v-show="activeTab === 'ui'" class="card mt-2">
    <div class="card-header">界面设置</div>
    <div class="form-grid">
      <label>登录页背景图</label>
      <div style="display:flex;gap:8px">
        <input :value="getp('appearance.login_bg')" @input="setp('appearance.login_bg',($event.target as any).value)" class="fi" style="flex:1" placeholder="https://... 或留空使用默认" />
        <label class="upload-btn">
          <i class="pi pi-upload" /> 上传
          <input type="file" accept="image/*" style="display:none" @change="uploadBg" />
        </label>
      </div>
      <span></span><span class="text-dim" style="font-size:11px">支持手动上传图片或填入 API 网络地址</span>
      <label>定时公告自动检查</label>
      <select :value="getp('tasks.auto_announce_enabled',false)" @change="setp('tasks.auto_announce_enabled',($event.target as any).value==='true')" class="fi">
        <option :value="false">禁用</option><option :value="true">启用</option>
      </select>
      <label>公告检查 cron</label><input :value="getp('tasks.auto_announce_cron','0 1 * * *')" @input="setp('tasks.auto_announce_cron',($event.target as any).value)" class="fi" />
      <!-- 主题切换（四套主题） -->
      <label>主题</label>
      <div class="theme-options">
        <label
          v-for="t in themeList"
          :key="t.id"
          class="theme-option"
          :class="{ active: store.theme === t.id }"
          @click="setTheme(t.id)"
        >
          <div class="theme-swatch-wrapper">
            <div class="theme-swatch" :style="{ background: t.colors.bg, borderColor: t.colors.border }">
              <div class="theme-primary-dot" :style="{ background: t.colors.primary }" />
            </div>
          </div>
          <span>{{ t.label }}</span>
        </label>
      </div>
      <!-- 界面语言选择 -->
      <label>界面语言</label>
      <Select
        v-model="selectedLocale"
        :options="localeOptions"
        optionLabel="label"
        optionValue="value"
        class="fi lang-select"
        style="width:200px"
        @change="onLocaleChange"
      />
    </div>
  </div>

  <!-- OCR -->
  <div v-show="activeTab === 'ocr'" class="card mt-2">
    <div class="card-header">OCR 识别设置</div>
    <p class="text-dim">三云调度（百度云+腾讯云主力，阿里云应急），各平台均有免费额度</p>
    <div class="form-grid">
      <label class="fieldset-label">百度云</label><span></span>
      <label>API Key</label>
      <input :value="getp('ocr.baidu_api_key')" @input="setp('ocr.baidu_api_key',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <label>Secret Key</label>
      <input :value="getp('ocr.baidu_secret_key')" @input="setp('ocr.baidu_secret_key',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <div class="fieldset-gap"></div>
      <label class="fieldset-label">腾讯云</label><span></span>
      <label>Secret ID</label>
      <input :value="getp('ocr.tencent_secret_id')" @input="setp('ocr.tencent_secret_id',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <label>Secret Key</label>
      <input :value="getp('ocr.tencent_secret_key')" @input="setp('ocr.tencent_secret_key',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <div class="fieldset-gap"></div>
      <label class="fieldset-label">阿里云（应急）</label><span></span>
      <label>Access Key ID</label>
      <input :value="getp('ocr.aliyun_access_key_id')" @input="setp('ocr.aliyun_access_key_id',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <label>Access Key Secret</label>
      <input :value="getp('ocr.aliyun_access_key_secret')" @input="setp('ocr.aliyun_access_key_secret',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
    </div>
  </div>

  <!-- 站点管理 -->
  <div v-show="activeTab === 'sites'" class="card mt-2">
    <div class="card-header">查询站点配置</div>
    <p class="text-dim mb-2">窗口上限 = 每轮冷却前最大请求数 | 日上限 = 当日累计超过后暂停使用（次日重置）</p>
    <div class="site-grid">
      <div v-for="s in sites" :key="s.name" class="site-card">
        <div class="site-head">
          <span class="site-priority">#{{ s.priority }}</span>
          <span class="site-name">{{ s.label }}</span>
          <Tag :value="s.name" severity="info" />
        </div>
        <div class="site-url text-mono text-dim">{{ s.url }}</div>
        <div class="site-limits">
          <div class="site-limit"><span class="lim-label">窗口上限</span><span class="lim-val">{{ s.maxRequests }} 次</span></div>
          <div class="site-limit"><span class="lim-label">日上限</span><span class="lim-val">{{ s.dailyLimit }} 次</span></div>
          <div class="site-limit"><span class="lim-label">冷却</span><span class="lim-val">10 分钟</span></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 用户 -->
  <div v-show="activeTab === 'users'" class="card mt-2">
    <div class="card-header">
      <span>用户管理</span>
      <div style="display:flex;gap:8px">
        <Button label="修改密码" icon="pi pi-lock" size="small" severity="secondary" @click="showPwd = true" />
        <Button label="添加" icon="pi pi-plus" size="small" @click="showAdd = true" />
      </div>
    </div>
    <p v-if="loadUsersErr" class="err-msg">{{ loadUsersErr }}</p>
    <DataView :value="users" size="small">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.id" class="p-2 border-bottom">
          <div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-light);align-items:center">
            <span style="min-width:100px;font-weight:500">{{ item.username }}</span>
            <span style="min-width:80px;font-size:13px;color:var(--text-dim)">{{ item.role }}</span>
            <span style="flex:1;font-size:12px;color:var(--text-dim)">{{ item.created_at }}</span>
            <Button v-if="canDelete(item)" icon="pi pi-trash" label="删除"
                    severity="danger" size="small" @click="confirmDelete(item)" />
          </div>
        </div>
      </template>
    </DataView>
  </div>

  <!-- API 令牌 -->
  <div v-show="activeTab === 'token'" class="card mt-2">
    <div class="card-header">
      <span>API 令牌</span>
      <span v-if="tokenErr" class="err-msg">{{ tokenErr }}</span>
    </div>
    <p class="text-dim mb-2">此令牌用于外部脚本或服务调用 PilotStd API。支持三种传递方式：<code>Authorization: Bearer</code> / <code>X-API-KEY</code> Header / <code>?token=</code> 查询参数。</p>
    <div class="token-display">
      <code class="token-value">{{ showToken ? token : maskToken(token) }}</code>
      <div class="token-actions">
        <Button :label="showToken ? '隐藏' : '显示完整令牌'" icon="pi pi-eye" size="small" severity="secondary" @click="showToken = !showToken" />
        <Button label="复制" icon="pi pi-copy" size="small" severity="secondary" @click="copyToken" />
        <Button label="刷新令牌" icon="pi pi-refresh" size="small" severity="warning" @click="showRefreshDlg = true" :loading="tokenLoading" />
      </div>
      <span v-if="tokenCopied" class="text-dim" style="font-size:12px;color:var(--success,#22c55e)">已复制到剪贴板</span>
    </div>
  </div>

  <!-- 刷新令牌确认弹窗 -->
  <Dialog v-model:visible="showRefreshDlg" header="刷新 API 令牌" :modal="true" :style="{width:'440px'}">
    <p style="margin-bottom:12px;line-height:1.6">刷新后<strong>旧令牌将立即失效</strong>，所有依赖旧令牌的脚本或服务需要更新为新令牌。</p>
    <p style="color:var(--text-dim);font-size:13px">确定继续吗？</p>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <Button label="取消" severity="secondary" @click="showRefreshDlg = false" />
      <Button label="确定刷新" severity="warning" @click="doRefreshToken" />
    </div>
  </Dialog>

  <!-- 熔断 -->
  <div v-show="activeTab === 'circuit'" class="card mt-2">
    <div class="card-header">熔断配置</div>
    <p class="text-dim mb-2">控制各站点适配器的熔断阈值、阶梯冻结时长和失败归零窗口。</p>
    <Message v-if="circuitErr" severity="error" :closable="false">{{ circuitErr }}</Message>
    <Message v-if="circuitSaved" severity="success" :closable="false">配置已保存</Message>
    <div class="form-grid" style="grid-template-columns:repeat(auto-fill, minmax(220px, 1fr))">
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>失败阈值</label>
        <InputNumber v-model="circuitCfg.failure_threshold" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第1阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[0]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第2阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[1]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第3阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[2]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>第4阶梯时长 (分钟)</label>
        <InputNumber v-model="circuitCfg.freeze_durations[3]" :min="1" show-buttons />
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <label>归零窗口 (小时)</label>
        <InputNumber v-model="circuitCfg.reset_window_hours" :min="1" show-buttons />
      </div>
    </div>
  </div>

  <!-- 通知 -->
  <div v-show="activeTab === 'notification'" class="card mt-2">
    <div class="card-header">通知配置</div>
    <NotificationConfig ref="notificationRef" />
    <hr style="margin:24px 0;border-color:var(--border)" />
    <div class="card-header" style="margin-bottom:12px">企业微信可信 IP 自动更新</div>
    <WechatTrustIP />
  </div>

  <!-- 时效性 -->
  <div v-show="activeTab === 'validity'" class="card mt-2">
    <div class="card-header">时效性检查</div>
    <ValidityConfig ref="validityRef" />
  </div>

  <!-- 系统 -->
  <div v-show="activeTab === 'system'" class="mt-2">
    <Card class="mb-3">
      <template #title>文件监控</template>
      <FileMonitor />
    </Card>
    <Card class="mb-3">
      <template #title>缓存管理</template>
      <CacheManager />
    </Card>
    <Card>
      <template #title>任务管理</template>
      <TaskManager />
    </Card>
  </div>

  <!-- 底部操作栏 -->
  <div class="settings-footer">
    <div class="footer-actions">
      <Button
        label="应用"
        icon="pi pi-refresh"
        severity="secondary"
        @click="applyCurrentTab"
        :loading="circuitLoading"
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

  <Dialog v-model:visible="showAdd" header="添加用户" :modal="true" :style="{width:'360px'}">
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="newUser.username" placeholder="用户名" class="fi" /><input v-model="newUser.password" type="password" placeholder="密码" class="fi" />
      <select v-model="newUser.role" class="fi"><option value="user">普通用户</option><option value="admin">管理员</option></select>
      <p v-if="userErr" class="error">{{ userErr }}</p>
      <div style="display:flex;gap:8px"><Button label="取消" severity="secondary" @click="showAdd=false" style="flex:1" /><Button label="添加" @click="doAdd" style="flex:1" /></div>
    </div>
  </Dialog>

  <Dialog v-model:visible="showPwd" :header="`修改密码 — ${store.username}`" :modal="true" :style="{width:'360px'}">
    <p class="text-dim" style="font-size:12px;margin-bottom:8px">正在修改用户 <strong>{{ store.username }}</strong> 的登录密码</p>
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="pwdForm.old" type="password" placeholder="旧密码" class="fi" />
      <input v-model="pwdForm.new" type="password" placeholder="新密码（至少4位）" class="fi" />
      <input v-model="pwdForm.confirm" type="password" placeholder="确认新密码" class="fi" />
      <p v-if="pwdErr" class="error">{{ pwdErr }}</p>
      <div style="display:flex;gap:8px"><Button label="取消" severity="secondary" @click="showPwd=false" style="flex:1" /><Button label="确认修改" @click="doChangePwd" style="flex:1" /></div>
    </div>
  </Dialog>
</template>

<style scoped>
/* 标签页导航 */
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

/* 卡片 */
.card {
  background: linear-gradient(135deg, var(--surface), var(--surface-raised));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-xs);
  transition: all var(--transition);
}
.card:hover {
  box-shadow: var(--shadow-sm);
}
.card-header {
  font-weight: 700;
  color: var(--text-heading);
  font-size: 15px;
  margin-bottom: 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--border);
}

/* 表单网格 */
.form-grid {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 14px 20px;
  align-items: center;
  font-size: 14px;
}
@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr; gap: 8px 0; }
  .form-grid label { margin-top: 8px; }
}
.form-grid label {
  color: var(--text-dim);
  font-weight: 500;
}

/* 表单输入框 */
.fi {
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius);
  font-size: 14px;
  outline: none;
  transition: all var(--transition);
  width: 100%;
}
.fi:focus {
  border-color: var(--primary);
  box-shadow: var(--focus-ring);
  background: var(--surface);
}
.fi:hover {
  border-color: var(--primary-border);
}

/* 语言下拉框——紧凑垂直内边距 */
.lang-select :deep(.p-select-label) { padding-top: 6px; padding-bottom: 6px; }

/* 上传按钮 */
.upload-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: all var(--transition);
}
.upload-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-bg);
}

/* 错误消息 */
.error { color: var(--danger); font-size: 12px; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin-left: 8px; }

/* 主题选择器 */
.theme-options { display: flex; gap: 20px; flex-wrap: wrap; }
.theme-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius);
  transition: all var(--transition);
}
.theme-option:hover { background: var(--selected); }
.theme-option span {
  font-size: 13px;
  color: var(--text-dim);
  transition: color var(--transition);
  font-weight: 500;
}
.theme-option.active span { color: var(--primary); font-weight: 700; }
.theme-swatch-wrapper { padding: 4px; }
.theme-swatch {
  width: 80px;
  height: 44px;
  border-radius: var(--radius);
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}
.theme-option:hover .theme-swatch {
  box-shadow: var(--shadow-sm);
  transform: scale(1.05);
}
.theme-primary-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: absolute;
  right: 8px;
  bottom: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
.theme-option.active .theme-swatch {
  border-color: var(--primary);
  box-shadow: var(--focus-ring), var(--shadow-md);
}

/* 站点网格 */
.site-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.site-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
}
.site-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: linear-gradient(180deg, var(--primary), var(--primary-hover));
  opacity: 0;
  transition: opacity var(--transition);
}
.site-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--primary-border);
  transform: translateY(-2px);
}
.site-card:hover::before { opacity: 1; }
.site-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.site-priority {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  background: var(--primary-bg);
  padding: 4px 10px;
  border-radius: 12px;
}
.site-name { font-size: 15px; font-weight: 600; color: var(--text-heading); }
.site-url { font-size: 12px; margin-bottom: 12px; }
.site-limits { display: flex; gap: 20px; }
.site-limit { display: flex; flex-direction: column; gap: 3px; }
.lim-label { font-size: 11px; color: var(--text-dim); font-weight: 500; }
.lim-val { font-size: 16px; font-weight: 700; color: var(--text-heading); font-family: var(--mono); }

.fieldset-gap { grid-column: 1 / -1; height: 12px; }
.mb-2 { margin-bottom: 16px; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }

/* 令牌显示 */
.token-display { display: flex; flex-direction: column; gap: 14px; }
.token-value {
  display: block;
  padding: 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--mono), 'Courier New', monospace;
  font-size: 14px;
  letter-spacing: 0.5px;
  word-break: break-all;
  color: var(--text-heading);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
}
.token-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

/* 底部操作栏 */
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
</style>
