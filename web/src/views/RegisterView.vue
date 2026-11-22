<script setup lang="ts">
defineOptions({ name: 'RegisterView' })
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { register } from '@/api/auth'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'

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
      <!-- name 属性与登录页保持一致：注册成功即视为登录态，e2e 复用同一套 input[name=username] 选择器 -->
      <AppInput v-model="username" name="username" size="l" :placeholder="t('register.username_ph')" class="login-input" @keyup.enter="submit" />
      <AppInput v-model="password" name="password" type="password" size="l" :placeholder="t('register.password_ph')" class="login-input" style="margin-top:var(--space-8)" @keyup.enter="submit" />
<AppButton
        :label="t('register.submit')"
        @click="submit"
        :loading="loading"
        style="width:100%;margin-top:var(--space-8)"
        size="m"
        type="primary"
      />
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
/* 布局只留宽度/间距；边框/底色/四态由 <AppInput size="l"> 承担（ui-system.md §11.4）。
   注册页是深色玻璃卡，DS 默认 surface 底在这里偏亮，故只保留底色覆盖（非尺寸/四态样式）。 */
.login-input {
  width: 100%;
  background: rgba(255,255,255,0.05); /* TODO: [Design Debt] rgba(255,255,255,0.05) 无精确令牌，暂不替换，待定令牌后统一处理 */
  box-sizing: border-box;
}
/* TODO: [Design Debt] rgba(255,255,255,0.3) 无精确令牌，暂不替换，待定令牌后统一处理 */
.login-input::placeholder { color: rgba(255,255,255,0.3); }
.error { color: var(--danger); font-size: var(--font-size-12); margin-top: var(--space-8); text-align: center; }
</style>
