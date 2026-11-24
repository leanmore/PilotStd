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
import { getApiErrorMessage } from '@/api/http'
import { useAppStore } from '@/stores/app'
import DataView from 'primevue/dataview'
import AppButton from '@/components/ui/AppButton.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppSelect from '@/components/ui/AppSelect.vue'

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

/** 角色下拉选项：label 走 i18n，value 是提交给后端的角色码 */
const roleOptions = computed(() => [
  { label: t('settings.users.role_user'), value: 'user' },
  { label: t('settings.users.role_admin'), value: 'admin' },
])

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
    userErr.value = getApiErrorMessage(e)
  }
}

// 2026-11-25 修复（D-7）：原实现无 try/catch —— 删除失败（权限/网络）时静默无提示；
// 且 userErr 只在「添加用户」对话框里渲染，删除错误必须落到列表区的可见位置。
const deleteError = ref('')

async function doDelete(id: number) {
  deleteError.value = ''
  try {
    await deleteUser(id)
    loadUsers()
  } catch (e: any) {
    deleteError.value = getApiErrorMessage(e)
  }
}

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
  <p v-if="deleteError" class="error mb-2">{{ deleteError }}</p>
  <div class="card mt-2">
    <div class="card-header">
      <span>{{ t('settings.users.title') }}</span>
      <div style="display:flex;gap:var(--space-8)">
<AppButton
          :label="t('settings.users.change_pwd')"
          icon="pi pi-lock"
          @click="showPwd = true"
          size="s"
          type="secondary"
        />
<AppButton
          :label="t('settings.users.add')"
          icon="pi pi-plus"
          @click="showAdd = true"
          size="s"
          type="secondary"
        />
      </div>
    </div>
    <p v-if="loadUsersErr" class="err-msg">{{ loadUsersErr }}</p>
    <DataView :value="users" size="small">
      <template #list="slotProps">
        <div v-for="item in slotProps.items" :key="item.id" class="p-2 border-bottom">
          <div style="display:flex;gap:var(--space-12);padding:var(--space-6) 0;border-bottom:1px solid var(--border-light);align-items:center">
            <span style="min-width:100px;font-weight:var(--font-weight-medium)">{{ item.username }}</span>
            <span style="min-width:80px;font-size:var(--font-size-13);color:var(--text-dim)">{{ item.role }}</span>
            <span style="flex:1;font-size:var(--font-size-12);color:var(--text-dim)">{{ item.created_at }}</span>
            <AppButton
        v-if="canDelete(item)"
        icon="pi pi-trash"
        :label="t('settings.users.delete')"
        type="danger"
        size="s"
        @click="confirmDelete(item)"
      />
          </div>
        </div>
      </template>
    </DataView>
  </div>

  <!-- 添加用户对话框 -->
  <AppDialog v-model:visible="showAdd" :header="t('settings.users.add_title')" :modal="true" :style="{width:'360px'}">
    <div style="display:flex;flex-direction:column;gap:var(--space-8)">
      <AppInput v-model="newUser.username" :placeholder="t('settings.users.field_username')" />
      <AppInput v-model="newUser.password" type="password" :placeholder="t('settings.users.field_password')" />
      <AppSelect v-model="newUser.role" :options="roleOptions" optionLabel="label" optionValue="value" />
      <p v-if="userErr" class="error">{{ userErr }}</p>
      <div style="display:flex;gap:var(--space-8)">
<AppButton
          :label="t('common.cancel')"
          @click="showAdd=false"
          style="flex:1"
          size="m"
          type="secondary"
        />
<AppButton
          :label="t('settings.users.add')"
          @click="doAdd"
          style="flex:1"
          size="m"
          type="secondary"
        />
      </div>
    </div>
  </AppDialog>

  <!-- 修改密码对话框 -->
  <AppDialog v-model:visible="showPwd" :header="t('settings.users.change_pwd_title', { name: store.username })" :modal="true" :style="{width:'360px'}">
    <p class="text-dim" style="font-size:var(--font-size-12);margin-bottom:var(--space-8)">{{ t('settings.users.change_pwd_hint_before') }}<strong>{{ store.username }}</strong>{{ t('settings.users.change_pwd_hint_after') }}</p>
    <div style="display:flex;flex-direction:column;gap:var(--space-8)">
      <AppInput v-model="pwdForm.old" type="password" :placeholder="t('settings.users.field_old_pwd')" />
      <AppInput v-model="pwdForm.new" type="password" :placeholder="t('settings.users.field_new_pwd')" />
      <AppInput v-model="pwdForm.confirm" type="password" :placeholder="t('settings.users.field_confirm_pwd')" />
      <p v-if="pwdErr" class="error">{{ pwdErr }}</p>
      <div style="display:flex;gap:var(--space-8)">
<AppButton
          :label="t('common.cancel')"
          @click="showPwd=false"
          style="flex:1"
          size="m"
          type="secondary"
        />
<AppButton
          :label="t('settings.users.change_pwd_ok')"
          @click="doChangePwd"
          style="flex:1"
          size="m"
          type="secondary"
        />
      </div>
    </div>
  </AppDialog>
  </div>
</template>

<style scoped>
@import './shared.css';

.p-2 { padding: var(--space-8); }
</style>
