// web/src/bootstrap/registerHttpHandlers.ts — 注册 http 全局处理器（401 登出 / 断网超时提示），打破 http ↔ stores/app 循环依赖
import type { App } from 'vue'
import { setNetworkErrorNotifier, setUnauthorizedHandler } from '@/api/http'
import { useAppStore } from '@/stores/app'
import { appToast } from '@/composables/useAppToast'
import router from '@/router'

export function registerHttpHandlers(app: App): void {
  // 保留形参（调用方签名不变）；本文件当前不需要 app 实例，
  // 提示走 appToast 全局单例，不再从 app.config.globalProperties 摸 $toast。
  void app

  setUnauthorizedHandler(() => {
    // 已在登录页时不要重复 push（会打断正在进行的重新登录）
    if (router.currentRoute.value.path === '/login') return
    const appStore = useAppStore()
    appStore.clearUser()
    router.push('/login')
  })

  // [FIX-401] 断网/超时由全局拦截器统一提示。
  // DS 模块四：提示走全局 appToast 单例（App.vue 挂载时 bindAppToast 注入），
  // 不再直接读 `app.config.globalProperties.$toast`（字符串键，类型与可测性都差）。
  setNetworkErrorNotifier((message: string) => {
    appToast.error({ summary: message })
  })
}
