<script setup lang="ts">
defineOptions({ name: 'SettingsTabUsers' })
/**
 * SettingsTabUsers — 用户管理 Tab
 * 自包含：拥有自己的状态、API 调用、对话框逻辑。
 * 依赖父组件提供 ConfirmDialog + Toast 作为全局服务。
 */
import { ref, onMounted, computed } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { getUsers, addUser, deleteUser, changePassword } from '@/api'
import { useAppStore } from '@/stores/app'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Dialog from 'primevue/dialog'

const ADMIN_ROLE = 'admin'

const store = useAppStore()
const confirm = useConfirm()

// ── 用户管理状态 ──
const users = ref<any[]>([])
const showAdd = ref(false)
const newUser = ref({ username: '', password: '', role: 'user' })
const userErr = ref('')
const loadUsersErr = ref('')

const currentUser = computed(() => users.value.find((u: any) => u.username === store.username) || null)

async function loadUsers() {
  try { const r = await getUsers(); users.value = r.users; loadUsersErr.value = '' }
  catch { loadUsersErr.value = '加载用户列表失败' }
}

async function doAdd() {
  if (newUser.value.username.toLowerCase() === 'admin') {
    userErr.value = '"admin" 为保留用户名，请使用其他名称'
    return
  }
  try {
    await addUser(newUser.value.username, newUser.value.password, newUser.value.role)
    showAdd.value = false
    newUser.value = { username: '', password: '', role: 'user' }
    userErr.value = ''
    loadUsers()
  } catch (e: any) {
    userErr.value = e.response?.data?.detail || '失败'
  }
}

async function doDelete(id: number) { await deleteUser(id); loadUsers() }

function canDelete(item: any): boolean {
  if (store.role !== ADMIN_ROLE) return false
  if (!currentUser.value || item.id === currentUser.value.id) return false
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
const showPwd = ref(false)
const pwdForm = ref({ old: '', new: '', confirm: '' })
const pwdErr = ref('')

async function doChangePwd() {
  pwdErr.value = ''
  if (!pwdForm.value.old || !pwdForm.value.new) { pwdErr.value = '请填写旧密码和新密码'; return }
  if (pwdForm.value.new.length < 4) { pwdErr.value = '新密码至少4个字符'; return }
  if (pwdForm.value.new !== pwdForm.value.confirm) { pwdErr.value = '两次输入的新密码不一致'; return }
  try {
    await changePassword(pwdForm.value.old, pwdForm.value.new)
    showPwd.value = false
    pwdForm.value = { old: '', new: '', confirm: '' }
    alert('密码已修改')
  } catch (e: any) { pwdErr.value = e.response?.data?.detail || '修改失败' }
}

onMounted(() => { loadUsers() })
</script>

<template>
  <div class="tab-content">
  <div class="card mt-2">
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

  <!-- 添加用户对话框 -->
  <Dialog v-model:visible="showAdd" header="添加用户" :modal="true" :style="{width:'360px'}">
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="newUser.username" placeholder="用户名" class="fi" />
      <input v-model="newUser.password" type="password" placeholder="密码" class="fi" />
      <select v-model="newUser.role" class="fi">
        <option value="user">普通用户</option>
        <option value="admin">管理员</option>
      </select>
      <p v-if="userErr" class="error">{{ userErr }}</p>
      <div style="display:flex;gap:8px">
        <Button label="取消" severity="secondary" @click="showAdd=false" style="flex:1" />
        <Button label="添加" @click="doAdd" style="flex:1" />
      </div>
    </div>
  </Dialog>

  <!-- 修改密码对话框 -->
  <Dialog v-model:visible="showPwd" :header="`修改密码 — ${store.username}`" :modal="true" :style="{width:'360px'}">
    <p class="text-dim" style="font-size:12px;margin-bottom:8px">正在修改用户 <strong>{{ store.username }}</strong> 的登录密码</p>
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="pwdForm.old" type="password" placeholder="旧密码" class="fi" />
      <input v-model="pwdForm.new" type="password" placeholder="新密码（至少4位）" class="fi" />
      <input v-model="pwdForm.confirm" type="password" placeholder="确认新密码" class="fi" />
      <p v-if="pwdErr" class="error">{{ pwdErr }}</p>
      <div style="display:flex;gap:8px">
        <Button label="取消" severity="secondary" @click="showPwd=false" style="flex:1" />
        <Button label="确认修改" @click="doChangePwd" style="flex:1" />
      </div>
    </div>
  </Dialog>
  </div>
</template>

<style scoped>
@import './shared.css';

.p-2 { padding: 8px; }
</style>
