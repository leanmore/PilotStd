// web/src/composables/useThemeSync.ts
// 同步应用主题与 PrimeVue 主题状态

import { watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { isDarkTheme } from '@/config/themes'

/**
 * 在组件 setup 中调用此函数，监听主题变化并同步到 PrimeVue
 * 建议在 App.vue 或根组件中调用一次
 *
 * PrimeVue 4.x 使用 Aura 主题时，会自动响应 html 元素的 data-p-theme 属性。
 * 我们通过修改该属性来触发 PrimeVue 内部的主题更新。
 */
export function useThemeSync() {
  const store = useAppStore()

  watch(
    () => store.theme,
    (newTheme) => {
      const dark = isDarkTheme(newTheme)

      // PrimeVue 4.x 通过 data-p-theme 属性控制暗色模式
      // 当 data-p-theme="dark" 时，Aura 预设自动应用暗色样式
      if (dark) {
        document.documentElement.setAttribute('data-p-theme', 'dark')
      } else {
        document.documentElement.removeAttribute('data-p-theme')
      }
    },
    { immediate: true },
  )
}
