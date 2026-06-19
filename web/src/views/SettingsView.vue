<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getUsers, addUser, deleteUser, changePassword, getSettings, putSettings, uploadFile } from '@/api'
import { useAppStore } from '@/stores/app'
const store = useAppStore()
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'

// ── 用户管理 ──
const users = ref<any[]>([]); const showAdd = ref(false)
const newUser = ref({ username: '', password: '', role: 'user' }); const userErr = ref(''); const loadUsersErr = ref('')
async function loadUsers() {
  try { const r = await getUsers(); users.value = r.users; loadUsersErr.value = '' } catch { loadUsersErr.value = '加载用户列表失败' }
}
async function doAdd() {
  try { await addUser(newUser.value.username, newUser.value.password, newUser.value.role); showAdd.value = false; newUser.value = { username: '', password: '', role: 'user' }; userErr.value = ''; loadUsers() }
  catch (e: any) { userErr.value = e.response?.data?.detail || '失败' }
}
async function doDelete(id: number) { await deleteUser(id); loadUsers() }

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
onMounted(() => { loadUsers(); loadCfg() })

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
]

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
      <!-- 主题切换（亮色/暗色双主题） -->
      <label>主题</label>
      <div class="theme-options">
        <label class="theme-option" :class="{ active: store.theme === 'light' }" @click="setTheme('light')">
          <div class="theme-swatch light">
            <i class="pi pi-sun" />
          </div>
          <span>亮色</span>
        </label>
        <label class="theme-option" :class="{ active: store.theme === 'dark' }" @click="setTheme('dark')">
          <div class="theme-swatch dark">
            <i class="pi pi-moon" />
          </div>
          <span>暗色</span>
        </label>
      </div>
    </div>
  </div>

  <!-- OCR -->
  <div v-show="activeTab === 'ocr'" class="card mt-2">
    <div class="card-header">OCR 识别设置</div>
    <p class="text-dim">三云调度（百度云+腾讯云主力，阿里云应急），各平台均有免费额度</p>
    <div class="form-grid">
      <label class="fieldset-label">百度云</label><span></span>
      <label>API Key</label>
      <input :value="getp('ocr.baidu_api_key')" @input="setp('ocr.baidu_api_key',($event.target as any).value)" class="fi" autocomplete="off" />
      <label>Secret Key</label>
      <input :value="getp('ocr.baidu_secret_key')" @input="setp('ocr.baidu_secret_key',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <div class="fieldset-gap"></div>
      <label class="fieldset-label">腾讯云</label><span></span>
      <label>Secret ID</label>
      <input :value="getp('ocr.tencent_secret_id')" @input="setp('ocr.tencent_secret_id',($event.target as any).value)" class="fi" />
      <label>Secret Key</label>
      <input :value="getp('ocr.tencent_secret_key')" @input="setp('ocr.tencent_secret_key',($event.target as any).value)" class="fi" type="password" autocomplete="off" />
      <div class="fieldset-gap"></div>
      <label class="fieldset-label">阿里云（应急）</label><span></span>
      <label>Access Key ID</label>
      <input :value="getp('ocr.aliyun_access_key_id')" @input="setp('ocr.aliyun_access_key_id',($event.target as any).value)" class="fi" />
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
            <Button v-if="item.username!=='admin'" icon="pi pi-trash"
                    severity="danger" size="small" text @click="doDelete(item.id)" />
          </div>
        </div>
      </template>
    </DataView>
  </div>

  <div class="mt-3" style="display:flex;align-items:center;gap:8px;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:8px">
      <Button label="保存设置" icon="pi pi-check" @click="saveCfg" />
      <Tag v-if="saved" value="已保存" severity="success" />
      <span v-if="cfgErr" class="err-msg">{{ cfgErr }}</span>
    </div>
    <span class="text-dim" style="font-size:11px">PilotStd v{{ cfg.version || '—' }}</span>
  </div>

  <Dialog v-model:visible="showAdd" header="添加用户" :modal="true" :style="{width:'360px'}">
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="newUser.username" placeholder="用户名" class="fi" /><input v-model="newUser.password" type="password" placeholder="密码" class="fi" />
      <select v-model="newUser.role" class="fi"><option value="user">普通用户</option><option value="admin">管理员</option></select>
      <p v-if="userErr" class="error">{{ userErr }}</p>
      <div style="display:flex;gap:8px"><Button label="取消" severity="secondary" @click="showAdd=false" style="flex:1" /><Button label="添加" @click="doAdd" style="flex:1" /></div>
    </div>
  </Dialog>

  <Dialog v-model:visible="showPwd" header="修改密码" :modal="true" :style="{width:'360px'}">
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
.tab-bar { display: flex; gap: 0; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; width: fit-content; }
.tab-bar button { padding: 8px 20px; border: none; background: none; color: var(--text-dim); cursor: pointer; font-size: 13px; border-right: 1px solid var(--border); transition: all var(--transition); }
.tab-bar button:last-child { border-right: none; }
.tab-bar button.active { background: var(--primary-bg); color: var(--primary); font-weight: 600; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow-xs); }
.card-header { font-weight: 600; color: var(--text-heading); font-size: 14px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.form-grid { display: grid; grid-template-columns: 150px 1fr; gap: 10px 16px; align-items: center; font-size: 13px; }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; } }
.form-grid label { color: var(--text-dim); }
.fi { padding: 8px 12px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); font-size: 13px; outline: none; transition: border-color var(--transition); }
.fi:focus { border-color: var(--primary); box-shadow: var(--focus-ring); }
.upload-btn { display: flex; align-items: center; gap: 4px; padding: 8px 14px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; white-space: nowrap; }
.upload-btn:hover { border-color: var(--primary); color: var(--primary); }
.error { color: var(--danger); font-size: 12px; }
.err-msg { color: var(--danger, #e74c3c); font-size: 12px; margin-left: 8px; }

/* 主题选择器 */
.theme-options { display: flex; gap: 12px; }
.theme-option { display: flex; flex-direction: column; align-items: center; gap: 6px; cursor: pointer; }
.theme-option span { font-size: 12px; color: var(--text-dim); }
.theme-option.active span { color: var(--primary); font-weight: 600; }
.theme-swatch {
  width: 56px;
  height: 40px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all var(--transition);
}
.theme-option.active .theme-swatch { border-color: var(--primary); box-shadow: var(--focus-ring); }
.theme-swatch.light { background: #f4f5fa; color: #f59e0b; }
.theme-swatch.dark { background: #111827; color: #818cf8; }

.site-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.site-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; transition: box-shadow 0.15s; }
.site-card:hover { box-shadow: var(--shadow-sm); border-color: var(--primary-border); }
.site-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.site-priority { font-size: 12px; font-weight: 700; color: var(--primary); background: var(--primary-bg); padding: 2px 8px; border-radius: 10px; }
.site-name { font-size: 14px; font-weight: 600; color: var(--text-heading); }
.site-url { font-size: 11px; margin-bottom: 10px; }
.site-limits { display: flex; gap: 16px; }
.site-limit { display: flex; flex-direction: column; gap: 2px; }
.lim-label { font-size: 11px; color: var(--text-dim); }
.lim-val { font-size: 15px; font-weight: 600; color: var(--text-heading); font-family: var(--mono); }
.fieldset-gap { grid-column: 1 / -1; height: 8px; }
.mb-2 { margin-bottom: 12px; }
.border-bottom { border-bottom: 1px solid var(--border-light, #e5e7eb); }
</style>
