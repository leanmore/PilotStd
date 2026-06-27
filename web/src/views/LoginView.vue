<script setup lang="ts">
defineOptions({ name: 'LoginView' })
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { login, getSettings } from '@/api'
import Button from 'primevue/button'

const username = ref('')
const password = ref('')
const error = ref('')
const bgUrl = ref('')
const router = useRouter()
const store = useAppStore()

async function submit() {
  try {
    await login(username.value, password.value)
    store.loggedIn = true; store.username = username.value; router.push('/')
  } catch { error.value = '用户名或密码错误' }
}

onMounted(async () => {
  try { const c = await getSettings(); bgUrl.value = (c.appearance?.login_bg || c.login_bg_url || '') as string } catch {}
})
</script>

<template>
  <div class="login-page" :style="bgUrl ? { backgroundImage: `url(${bgUrl})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}">
    <div class="login-card">
      <div class="login-brand"><span class="brand-icon">&#9678;</span><h1>PilotStd</h1></div>
      <p class="hint">标准管理控制台</p>
      <input v-model="username" placeholder="用户名" class="login-input" @keyup.enter="submit" />
      <input v-model="password" type="password" placeholder="密码" class="login-input" style="margin-top:8px" @keyup.enter="submit" />
      <Button label="登 录" @click="submit" severity="primary" style="width:100%;margin-top:8px" />
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.login-page { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: var(--bg); }
.login-card { width: 340px; padding: 44px 36px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); text-align: center; }
.login-brand { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 4px; }
.brand-icon { color: var(--accent); font-size: 22px; }
.login-brand h1 { font-size: 20px; font-weight: 600; color: var(--text-heading); }
.login-input { width: 100%; padding: 10px 14px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius); font-size: 14px; outline: none; margin-top: 12px; box-sizing: border-box; }
.login-input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); }
.error { color: var(--danger); font-size: 13px; margin-top: 8px; }
</style>
