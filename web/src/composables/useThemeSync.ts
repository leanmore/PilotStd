// web/src/composables/useThemeSync.ts
// 同步应用主题与 PrimeVue Aura 色板 — 运行时动态注入 surface 颜色

import { watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { isDarkTheme, THEMES } from '@/config/themes'
import { updateSurfacePalette } from '@primeuix/themes'

/**
 * 将当前主题的 surface 颜色动态注入 Aura 暗色色板。
 * Aura 暗色模式使用 surface.900 作为卡片/浮层背景、surface.800 作为 hover 背景、
 * surface.950 作为表单字段背景、surface.700 作为 disabled 背景。
 * 亮色模式使用 surface.0 作为卡片背景，Aura 默认值（白色）已足够接近项目主题。
 */
function syncDarkSurface(themeId: string) {
  const tc = THEMES[themeId]
  if (!tc) return

  // updateSurfacePalette 运行时支持 {dark, light} 嵌套格式，但类型声明仅覆盖扁平 ColorScale
  updateSurfacePalette({
    dark: {
      900: tc.colors.surface,                                 // surface.900 → 卡片/浮层/弹窗背景
      800: tc.colors.surfaceRaised ?? tc.colors.surface,      // surface.800 → hover 背景（fallback → surface）
      950: tc.colors.bg,                                      // surface.950 → 表单字段背景
      700: tc.colors.disabledBg ?? tc.colors.surface,         // surface.700 → disabled / 次要背景（fallback → surface）
    },
  } as any)
}

/**
 * 在根组件 setup 中调用此函数，监听主题变化并同步到 PrimeVue。
 * 建议在 App.vue 中调用一次。
 *
 * PrimeVue 4.x 使用 Aura 主题时，通过 data-p-theme 属性控制明暗模式。
 * 同时通过 updateSurfacePalette() 将项目自定义主题的 surface 颜色注入 Aura 暗色色板，
 * 确保 dark/blue 主题的卡片背景色与项目设计 token 一致。
 */
export function useThemeSync() {
  const store = useAppStore()

  watch(
    () => store.theme,
    (newTheme) => {
      const dark = isDarkTheme(newTheme)

      // PrimeVue 4.x 通过 data-p-theme 属性控制暗色模式
      if (dark) {
        document.documentElement.setAttribute('data-p-theme', 'dark')
      } else {
        document.documentElement.removeAttribute('data-p-theme')
      }

      // 运行时同步项目 surface 色到 Aura 色板
      if (dark) {
        syncDarkSurface(newTheme)
      }
    },
    { immediate: true },
  )
}
