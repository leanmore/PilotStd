<script setup lang="ts">
/**
 * SettingsTabToken — API 令牌管理 Tab
 * 自包含：拥有自己的状态、API 调用、令牌显隐/复制/刷新逻辑。
 * 依赖父组件提供 Toast 作为全局服务。
 */
import { ref, onMounted } from 'vue'
import { getToken, refreshToken } from '@/api'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

defineOptions({ name: 'SettingsTabToken' })

// ── API 令牌状态 ──
const token = ref('')
const tokenErr = ref('')
const tokenLoading = ref(false)
const showToken = ref(false)
const tokenCopied = ref(false)
const showRefreshDlg = ref(false)

function maskToken(t: string) {
  if (!t || t.length <= 12) return t ? t.slice(0, 8) + '****' : ''
  return t.slice(0, 8) + '****' + t.slice(-4)
}

async function loadToken() {
  try { const r = await getToken(); token.value = r.token; tokenErr.value = '' }
  catch { tokenErr.value = '加载令牌失败（需要管理员权限）' }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(token.value)
    tokenCopied.value = true
  } catch {
    // 降级：HTTP 环境下 clipboard API 不可用，使用 textarea + execCommand
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
    tokenErr.value = '刷新失败，请确认管理员权限'
    tokenLoading.value = false
  }
}

onMounted(() => { loadToken() })
</script>

<template>
  <div class="tab-content">
  <div class="card mt-2">
    <div class="card-header">
      <span>API 令牌</span>
      <span v-if="tokenErr" class="err-msg">{{ tokenErr }}</span>
    </div>
    <p class="text-dim mb-2">此令牌用于外部脚本或服务调用 PilotStd API。支持三种传递方式：<code>Authorization: Bearer</code> / <code>X-API-KEY</code> Header / <code>?token=</code> 查询参数。</p>
    <div class="token-display">
      <code class="token-value">{{ showToken ? token : maskToken(token) }}</code>
      <div class="token-actions">
        <Button :label="showToken ? '隐藏' : '显示完整令牌'" icon="pi pi-eye" size="small" severity="secondary" @click="showToken = !showToken" />
        <Button label="复制" icon="pi pi-copy" size="small" severity="secondary" @click="copyToken" />
        <Button label="刷新令牌" icon="pi pi-refresh" size="small" severity="warning" @click="showRefreshDlg = true" :loading="tokenLoading" />
      </div>
      <span v-if="tokenCopied" class="text-dim" style="font-size:12px;color:var(--success,#22c55e)">已复制到剪贴板</span>
    </div>
  </div>

  <!-- 刷新令牌确认弹窗 -->
  <Dialog v-model:visible="showRefreshDlg" header="刷新 API 令牌" :modal="true" :style="{width:'440px'}">
    <p style="margin-bottom:12px;line-height:1.6">刷新后<strong>旧令牌将立即失效</strong>，所有依赖旧令牌的脚本或服务需要更新为新令牌。</p>
    <p style="color:var(--text-dim);font-size:13px">确定继续吗？</p>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <Button label="取消" severity="secondary" @click="showRefreshDlg = false" />
      <Button label="确定刷新" severity="warning" @click="doRefreshToken" />
    </div>
  </Dialog>
  </div>
</template>

<style scoped>
@import './shared.css';
</style>
