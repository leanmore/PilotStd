<script setup lang="ts">
defineOptions({ name: 'LoginView' })
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import { login, getLoginBackground } from '@/api'
import { notifyAuthChanged } from '@/api/http'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'

const { t } = useI18n()

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
    img.onerror = () => console.warn('登录页背景图加载失败，使用默认背景', url) // i18n-allow: 开发者日志：背景图加载失败后回退默认背景
    img.src = url
  } catch (err) {
    console.warn('登录页背景图 URL 获取失败，使用默认背景', err) // i18n-allow: 开发者日志：背景图 URL 获取失败后回退默认背景
  }
}
void loadBackground()

async function submit() {
  try {
    const r = await login(username.value, password.value)
    // 登录成功后让“登录前发出”的在途请求失效，避免它们 401 时把页面踢回 /login
    notifyAuthChanged()
    store.loggedIn = true
    store.username = username.value
    store.role = r.role || 'user'
    router.push('/')
  } catch { error.value = t('login.err_invalid') }
}
</script>

<template>
  <div class="login-page" :style="bgUrl ? { backgroundImage: `url(${bgUrl})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}">
    <div class="login-card">
      <div class="login-brand"><span class="brand-icon">&#9678;</span><h1>PilotStd</h1></div>
      <p class="hint">{{ t('login.hint') }}</p>
      <!-- name 属性必须保留：e2e（announce-pagination.mjs / audit-ui-behavior.spec.ts）依赖 input[name=username] -->
      <AppInput v-model="username" name="username" size="l" :placeholder="t('login.username')" class="login-input" @keyup.enter="submit" />
      <AppInput v-model="password" name="password" type="password" size="l" :placeholder="t('login.password')" class="login-input" style="margin-top:var(--space-8)" @keyup.enter="submit" />
<AppButton
        :label="t('login.submit_spaced')"
        native-type="submit"
        @click="submit"
        style="width:100%;margin-top:var(--space-8)"
        size="m"
        type="primary"
      />
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
/* 未配置背景图或加载失败时的默认渐变兜底 */
/* TODO: [Design Debt] A-52 — linear-gradient(135deg, #667eea 0%, #764ba2 100%) 无精确令牌，暂不替换，待定令牌后统一处理 */
.login-page { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
/* TODO: [Design Debt] A-52 — 44px 36px 无精确令牌，暂不替换，待定令牌后统一处理 */
.login-card { width: 340px; padding: 44px 36px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); text-align: center; }
.login-brand { display: flex; align-items: center; justify-content: center; gap: var(--space-8); margin-bottom: var(--space-4); }
.brand-icon { color: var(--accent); font-size: var(--font-size-22); }
.login-brand h1 { font-size: var(--font-size-20); font-weight: var(--font-weight-semibold); color: var(--text-heading); }
/* 布局只留尺寸/间距；输入框的四态与内边距由 <AppInput size="l"> 承担（ui-system.md §11.4） */
.login-input { width: 100%; margin-top: var(--space-12); box-sizing: border-box; }
.error { color: var(--danger); font-size: var(--font-size-13); margin-top: var(--space-8); }
</style>
