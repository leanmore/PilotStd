<script setup lang="ts">
defineOptions({ name: 'RegisterView' })
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { register } from '@/api/auth'
import Button from 'primevue/button'

const { t } = useI18n()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const router = useRouter()

async function submit() {
  if (!username.value || !password.value) {
    error.value = t('register.err_required')
    return
  }
  loading.value = true
  try {
    await register(username.value, password.value)
    router.push('/')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'string') {
      error.value = detail
    } else if (e.response?.status === 409) {
      error.value = t('register.err_exists')
    } else if (e.response?.status === 429) {
      error.value = t('register.err_rate_limit')
    } else if (e.response?.status === 403) {
      error.value = t('register.err_disabled')
    } else {
      error.value = t('register.err_failed')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand"><span class="brand-icon">&#9678;</span><h1>PilotStd</h1></div>
      <p class="hint">{{ t('register.hint') }}</p>
      <input v-model="username" :placeholder="t('register.username_ph')" class="login-input" @keyup.enter="submit" />
      <input v-model="password" type="password" :placeholder="t('register.password_ph')" class="login-input" style="margin-top:var(--space-8)" @keyup.enter="submit" />
      <Button :label="t('register.submit')" @click="submit" severity="primary" :loading="loading" style="width:100%;margin-top:var(--space-8)" />
      <p v-if="error" class="error">{{ error }}</p>
      <p class="hint" style="margin-top:var(--space-16)">
        {{ t('register.have_account') }}<router-link to="/login" class="text-primary">{{ t('register.back_to_login') }}</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* 复用登录页样式 */
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  /* TODO: [Design Debt] linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%) 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}
.login-card {
  /* TODO: [Design Debt] rgba(255,255,255,0.06) 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: rgba(255,255,255,0.06); backdrop-filter: blur(16px); border-radius: var(--ds-radius-xl);
  /* TODO: [Design Debt] 1px solid rgba(255,255,255,0.1) 无精确令牌，暂不替换，待定令牌后统一处理 */
  padding: var(--space-40); width: 380px; max-width: 90vw; border: 1px solid rgba(255,255,255,0.1);
}
.login-brand { display: flex; align-items: center; gap: var(--space-12); margin-bottom: var(--space-8); }
.brand-icon { font-size: var(--font-size-28); color: var(--primary); }
/* TODO: [Design Debt] #fff 无精确令牌，暂不替换，待定令牌后统一处理 */
.login-brand h1 { font-size: var(--font-size-24); font-weight: var(--font-weight-bold); color: #fff; margin: 0; }
/* TODO: [Design Debt] rgba(255,255,255,0.5) 无精确令牌，暂不替换，待定令牌后统一处理 */
.hint { color: rgba(255,255,255,0.5); font-size: var(--font-size-13); margin-bottom: var(--space-16); text-align: center; }
.login-input {
  /* TODO: [Design Debt] 1px solid rgba(255,255,255,0.1) 无精确令牌，暂不替换，待定令牌后统一处理 */
  width: 100%; padding: var(--space-12); border-radius: var(--ds-radius-md); border: 1px solid rgba(255,255,255,0.1);
  /* TODO: [Design Debt] #fff 无精确令牌，暂不替换，待定令牌后统一处理 */
  /* TODO: [Design Debt] rgba(255,255,255,0.05) 无精确令牌，暂不替换，待定令牌后统一处理 */
  background: rgba(255,255,255,0.05); color: #fff; font-size: var(--font-size-14); outline: none;
  box-sizing: border-box;
}
/* TODO: [Design Debt] rgba(255,255,255,0.3) 无精确令牌，暂不替换，待定令牌后统一处理 */
.login-input::placeholder { color: rgba(255,255,255,0.3); }
.login-input:focus { border-color: var(--primary); }
.error { color: var(--danger); font-size: var(--font-size-12); margin-top: var(--space-8); text-align: center; }
</style>
