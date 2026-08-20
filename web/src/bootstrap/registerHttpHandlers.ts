// web/src/bootstrap/registerHttpHandlers.ts — 注册 http 全局处理器（401 登出 / 断网超时提示），打破 http ↔ stores/app 循环依赖
import type { App } from 'vue'
import { setNetworkErrorNotifier, setUnauthorizedHandler } from '@/api/http'
import { useAppStore } from '@/stores/app'
import router from '@/router'

type ToastLike = { add(message: { severity: string; summary: string; life: number }): void }

export function registerHttpHandlers(app: App): void {
  setUnauthorizedHandler(() => {
    const appStore = useAppStore()
    appStore.clearUser()
    router.push('/login')
  })
  // [FIX-401] 断网/超时由全局拦截器统一提示；$toast 由 ToastService 注入，注册时惰性读取
  setNetworkErrorNotifier((message: string) => {
    const toast = (app.config.globalProperties as unknown as { $toast?: ToastLike }).$toast
    if (toast) {
      toast.add({ severity: 'error', summary: message, life: 3000 })
    }
  })
}
