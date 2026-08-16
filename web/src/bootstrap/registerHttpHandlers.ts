// web/src/bootstrap/registerHttpHandlers.ts — 注册 http 401 处理器，打破 http ↔ stores/app 循环依赖
import { setUnauthorizedHandler } from '@/api/http'
import { useAppStore } from '@/stores/app'
import router from '@/router'

export function registerHttpHandlers(): void {
  setUnauthorizedHandler(() => {
    const appStore = useAppStore()
    appStore.clearUser()
    router.push('/login')
  })
}
