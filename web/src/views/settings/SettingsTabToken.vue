<script setup lang="ts">
/**
 * SettingsTabToken — API 令牌管理 Tab
 * 自包含：拥有自己的状态、API 调用、令牌显隐/复制/刷新逻辑。
 * 依赖父组件提供 Toast 作为全局服务。
 */
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getToken, refreshToken } from '@/api'
import http from '@/api/http'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'

defineOptions({ name: 'SettingsTabToken' })

const { t } = useI18n()

// ── API 令牌状态 ──
const token = ref('')
const tokenErr = ref('')
const tokenLoading = ref(false)
const showToken = ref(false)
const tokenCopied = ref(false)
const showRefreshDlg = ref(false)

// ── GitHub Token 状态 ──
const ghToken = ref('')
const ghTokenSaved = ref(false)
const ghTokenSaving = ref(false)
const ghTokenErr = ref('')

function maskToken(t: string) {
  if (!t || t.length <= 12) return t ? t.slice(0, 8) + '****' : ''
  return t.slice(0, 8) + '****' + t.slice(-4)
}

async function loadToken() {
  try { const r = await getToken('/settings'); token.value = r.token; tokenErr.value = '' }
  catch { tokenErr.value = t('settings.token.load_failed') }
}

async function loadGhToken() {
  try {
    const r = await http.get('/settings', { routeTag: '/settings' })
    ghToken.value = r.data?.updater?.github_token || ''
  } catch { /* 非关键 */ }
}

async function saveGhToken() {
  ghTokenSaving.value = true; ghTokenErr.value = ''
  try {
    await http.put('/settings', { updater: { github_token: ghToken.value } })
    ghTokenSaved.value = true
    setTimeout(() => ghTokenSaved.value = false, 2000)
  } catch {
    ghTokenErr.value = t('common.save_failed')
  } finally {
    ghTokenSaving.value = false
  }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(token.value)
    tokenCopied.value = true
  } catch {
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
  try {
    const r = await refreshToken()
    token.value = r.token
    showToken.value = true
    showRefreshDlg.value = false
    tokenLoading.value = false
  } catch {
    tokenErr.value = t('settings.token.refresh_failed')
    tokenLoading.value = false
  }
}

onMounted(() => { loadToken(); loadGhToken() })
</script>

<template>
  <div class="tab-content">
  <div class="card mt-2">
    <div class="card-header">
      <span>{{ t('settings.token.title') }}</span>
      <span v-if="tokenErr" class="err-msg">{{ tokenErr }}</span>
    </div>
    <p class="text-dim mb-2">{{ t('settings.token.desc_before') }}<code>Authorization: Bearer</code> / <code>X-API-KEY</code> Header / <code>?token=</code>{{ t('settings.token.desc_after') }}</p>
    <div class="token-display">
      <code class="token-value">{{ showToken ? token : maskToken(token) }}</code>
      <div class="token-actions">
        <Button :label="showToken ? t('settings.token.hide') : t('settings.token.show')" icon="pi pi-eye" size="small" severity="secondary" @click="showToken = !showToken" />
        <Button :label="t('settings.token.copy')" icon="pi pi-copy" size="small" severity="secondary" @click="copyToken" />
        <Button :label="t('settings.token.refresh')" icon="pi pi-refresh" size="small" severity="warning" @click="showRefreshDlg = true" :loading="tokenLoading" />
      </div>
      <span v-if="tokenCopied" class="text-dim" style="font-size:12px;color:var(--success,#22c55e)">{{ t('settings.token.copied') }}</span>
    </div>
  </div>

  <!-- GitHub Token -->
  <div class="card mt-2">
    <div class="card-header">GitHub Token</div>
    <p class="text-dim mb-2">{{ t('settings.token.gh_hint') }}</p>
    <Message v-if="!ghToken" severity="warn" :closable="false" style="margin-bottom:8px">
      {{ t('settings.token.gh_warning') }}
    </Message>
    <div style="display:flex;gap:8px;align-items:center">
      <input
        v-model="ghToken"
        type="password"
        class="fi"
        style="flex:1"
        placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
      />
      <Button :label="t('common.save')" icon="pi pi-save" size="small" @click="saveGhToken" :loading="ghTokenSaving" />
    </div>
    <span v-if="ghTokenSaved" style="font-size:12px;color:var(--success)">{{ t('common.saved') }}</span>
    <span v-if="ghTokenErr" style="font-size:12px;color:var(--danger)">{{ ghTokenErr }}</span>
  </div>

  <!-- 刷新令牌确认弹窗 -->
  <Dialog v-model:visible="showRefreshDlg" :header="t('settings.token.refresh_title')" :modal="true" :style="{width:'440px'}">
    <p style="margin-bottom:12px;line-height:1.6">{{ t('settings.token.refresh_warn_before') }}<strong>{{ t('settings.token.refresh_warn_strong') }}</strong>{{ t('settings.token.refresh_warn_after') }}</p>
    <p style="color:var(--text-dim);font-size:13px">{{ t('settings.token.refresh_confirm') }}</p>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <Button :label="t('common.cancel')" severity="secondary" @click="showRefreshDlg = false" />
      <Button :label="t('settings.token.refresh_ok')" severity="warning" @click="doRefreshToken" />
    </div>
  </Dialog>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
