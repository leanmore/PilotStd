<script setup lang="ts">
defineOptions({ name: 'SettingsTabUsers' })
/**
 * SettingsTabUsers — 用户管理 Tab
 * 自包含：拥有自己的状态、API 调用、对话框逻辑。
 * 依赖父组件提供 ConfirmDialog + Toast 作为全局服务。
 */
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'primevue/useconfirm'
import { getUsers, addUser, deleteUser, changePassword } from '@/api'
import { useAppStore } from '@/stores/app'
import Button from 'primevue/button'
import DataView from 'primevue/dataview'
import Dialog from 'primevue/dialog'

const ADMIN_ROLE = 'admin'

const { t } = useI18n()
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
  try { const r = await getUsers('/settings'); users.value = r.users; loadUsersErr.value = '' }
  catch { loadUsersErr.value = t('settings.users.load_failed') }
}

async function doAdd() {
  if (newUser.value.username.toLowerCase() === 'admin') {
    userErr.value = t('settings.users.username_reserved')
    return
  }
  try {
    await addUser(newUser.value.username, newUser.value.password, newUser.value.role)
    showAdd.value = false
    newUser.value = { username: '', password: '', role: 'user' }
    userErr.value = ''
    loadUsers()
  } catch (e: any) {
    userErr.value = e.response?.data?.detail || t('settings.users.add_failed')
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
    message: t('settings.users.delete_confirm', { name: item.username }),
    header: t('settings.users.delete_title'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('settings.users.delete_ok'),
    acceptClass: 'p-button-danger',
    rejectLabel: t('common.cancel'),
    accept: () => doDelete(item.id),
  })
}

// ── 修改密码 ──
const showPwd = ref(false)
const pwdForm = ref({ old: '', new: '', confirm: '' })
const pwdErr = ref('')

async function doChangePwd() {
  pwdErr.value = ''
  if (!pwdForm.value.old || !pwdForm.value.new) { pwdErr.value = t('settings.users.pwd_required'); return }
  if (pwdForm.value.new.length < 4) { pwdErr.value = t('settings.users.pwd_too_short'); return }
  if (pwdForm.value.new !== pwdForm.value.confirm) { pwdErr.value = t('settings.users.pwd_mismatch'); return }
  try {
    await changePassword(pwdForm.value.old, pwdForm.value.new)
    showPwd.value = false
    pwdForm.value = { old: '', new: '', confirm: '' }
    alert(t('settings.users.pwd_changed'))
  } catch (e: any) { pwdErr.value = e.response?.data?.detail || t('settings.users.pwd_failed') }
}

onMounted(() => { loadUsers() })
</script>

<template>
  <div class="tab-content">
  <div class="card mt-2">
    <div class="card-header">
      <span>{{ t('settings.users.title') }}</span>
      <div style="display:flex;gap:8px">
        <Button :label="t('settings.users.change_pwd')" icon="pi pi-lock" size="small" severity="secondary" @click="showPwd = true" />
        <Button :label="t('settings.users.add')" icon="pi pi-plus" size="small" @click="showAdd = true" />
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
            <Button v-if="canDelete(item)" icon="pi pi-trash" :label="t('settings.users.delete')"
                    severity="danger" size="small" @click="confirmDelete(item)" />
          </div>
        </div>
      </template>
    </DataView>
  </div>

  <!-- 添加用户对话框 -->
  <Dialog v-model:visible="showAdd" :header="t('settings.users.add_title')" :modal="true" :style="{width:'360px'}">
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="newUser.username" :placeholder="t('settings.users.field_username')" class="fi" />
      <input v-model="newUser.password" type="password" :placeholder="t('settings.users.field_password')" class="fi" />
      <select v-model="newUser.role" class="fi">
        <option value="user">{{ t('settings.users.role_user') }}</option>
        <option value="admin">{{ t('settings.users.role_admin') }}</option>
      </select>
      <p v-if="userErr" class="error">{{ userErr }}</p>
      <div style="display:flex;gap:8px">
        <Button :label="t('common.cancel')" severity="secondary" @click="showAdd=false" style="flex:1" />
        <Button :label="t('settings.users.add')" @click="doAdd" style="flex:1" />
      </div>
    </div>
  </Dialog>

  <!-- 修改密码对话框 -->
  <Dialog v-model:visible="showPwd" :header="t('settings.users.change_pwd_title', { name: store.username })" :modal="true" :style="{width:'360px'}">
    <p class="text-dim" style="font-size:12px;margin-bottom:8px">{{ t('settings.users.change_pwd_hint_before') }}<strong>{{ store.username }}</strong>{{ t('settings.users.change_pwd_hint_after') }}</p>
    <div style="display:flex;flex-direction:column;gap:8px">
      <input v-model="pwdForm.old" type="password" :placeholder="t('settings.users.field_old_pwd')" class="fi" />
      <input v-model="pwdForm.new" type="password" :placeholder="t('settings.users.field_new_pwd')" class="fi" />
      <input v-model="pwdForm.confirm" type="password" :placeholder="t('settings.users.field_confirm_pwd')" class="fi" />
      <p v-if="pwdErr" class="error">{{ pwdErr }}</p>
      <div style="display:flex;gap:8px">
        <Button :label="t('common.cancel')" severity="secondary" @click="showPwd=false" style="flex:1" />
        <Button :label="t('settings.users.change_pwd_ok')" @click="doChangePwd" style="flex:1" />
      </div>
    </div>
  </Dialog>
  </div>
</template>

<style scoped>
@import './shared.css';

.p-2 { padding: 8px; }
</style>
