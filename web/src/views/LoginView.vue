<script setup lang="ts">
defineOptions({ name: 'LoginView' })
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { login, getLoginBackground } from '@/api'
import Button from 'primevue/button'

const username = ref('')
const password = ref('')
const error = ref('')
const bgUrl = ref('')
const router = useRouter()
const store = useAppStore()

// 背景图两阶段加载（解耦 + 提前）：
// 阶段1 拉取背景图 URL —— 走公开接口 /api/login-background（白名单放行，无 token 可用），
//       不再依赖 admin-only 的 /api/settings（未登录 401 / 非 admin 403 导致背景图延迟或缺失）
// 阶段2 new Image() 预加载图片，onload 后才写入 bgUrl，避免渲染时闪空白
// 在 <script setup> 顶层立即执行，早于 onMounted，随组件创建即刻发起
async function loadBackground() {
  try {
    const { url } = await getLoginBackground()
    // file:// 为桌面端本地文件路径，浏览器无法加载，跳过
    if (!url || url.startsWith('file://')) return
    const img = new Image()
    img.onload = () => { bgUrl.value = url }
    img.onerror = () => console.warn('登录页背景图加载失败，使用默认背景', url)
    img.src = url
  } catch (err) {
    console.warn('登录页背景图 URL 获取失败，使用默认背景', err)
  }
}
void loadBackground()

async function submit() {
  try {
    const r = await login(username.value, password.value)
    store.loggedIn = true
    store.username = username.value
    store.role = r.role || 'user'
    router.push('/')
  } catch { error.value = '用户名或密码错误' }
}
</script>

<template>
  <div class="login-page" :style="bgUrl ? { backgroundImage: `url(${bgUrl})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}">
    <div class="login-card">
      <div class="login-brand"><span class="brand-icon">&#9678;</span><h1>PilotStd</h1></div>
      <p class="hint">标准管理控制台</p>
      <input v-model="username" name="username" placeholder="用户名" class="login-input" @keyup.enter="submit" />
      <input v-model="password" name="password" type="password" placeholder="密码" class="login-input" style="margin-top:8px" @keyup.enter="submit" />
      <Button label="登 录" type="submit" @click="submit" severity="primary" style="width:100%;margin-top:8px" />
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
/* 未配置背景图或加载失败时的默认渐变兜底 */
.login-page { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.login-card { width: 340px; padding: 44px 36px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); text-align: center; }
.login-brand { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 4px; }
.brand-icon { color: var(--accent); font-size: 22px; }
.login-brand h1 { font-size: 20px; font-weight: 600; color: var(--text-heading); }
.login-input { width: 100%; padding: 10px 14px; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius); font-size: 14px; outline: none; margin-top: 12px; box-sizing: border-box; }
.login-input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); }
.error { color: var(--danger); font-size: 13px; margin-top: 8px; }
</style>
