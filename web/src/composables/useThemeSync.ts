// web/src/composables/useThemeSync.ts
// 同步应用主题与 PrimeVue Aura 色板 — 运行时动态注入 surface 颜色
// Tech-Debt #8：新增 text/content 系 token 注入（见 aura-token-map.ts）

import { watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { isDarkTheme, THEMES } from '@/config/themes'
import { updateSurfacePalette } from '@primeuix/themes'
import { AURA_TOKEN_MAP } from '@/theme/aura-token-map'

/**
 * 将当前主题的 surface 颜色动态注入 Aura 色板（亮色 + 暗色同时更新）。
 *
 * Aura 暗色模式使用 surface.900 作为卡片/浮层背景、surface.800 作为 hover 背景、
 * surface.950 作为表单字段背景、surface.700 作为 disabled 背景。
 * 亮色模式使用 surface.0 作为卡片背景、surface.50 作为 hover 背景、
 * surface.100 作为表单字段背景。
 *
 * updateSurfacePalette 运行时支持 {dark, light} 嵌套格式，但类型声明仅覆盖扁平 ColorScale。
 * 必须同时设置 light 和 dark，因为该函数实际修改 :root 层级全局令牌
 * （非 [data-p-theme] 作用域），仅同步暗色会导致亮色模式继承暗色 surface 值。
 */
function syncSurfacePalette(themeId: string) {
  const tc = THEMES[themeId]
  if (!tc) return

  updateSurfacePalette({
    dark: {
      900: tc.colors.surface,                                 // surface.900 → 卡片/浮层/弹窗背景
      800: tc.colors.surfaceRaised ?? tc.colors.surface,      // surface.800 → hover 背景（fallback → surface）
      950: tc.colors.bg,                                      // surface.950 → 表单字段背景
      700: tc.colors.disabledBg ?? tc.colors.surface,         // surface.700 → disabled / 次要背景（fallback → surface）
    },
    light: {
      0: tc.colors.surface,                                   // surface.0 → 卡片/浮层/弹窗背景
      50: tc.colors.surfaceRaised ?? tc.colors.bg,            // surface.50 → hover 背景（fallback → bg）
      100: tc.colors.bg,                                      // surface.100 → 表单字段背景 / 次要区域
    },
  } as any)
}

/** 所有映射表中出现过的 Aura token 名（主题切换时全量清理，回退 Aura 默认样式表值） */
const ALL_MAPPED_TOKENS = new Set<string>(Object.values(AURA_TOKEN_MAP).flatMap((m) => Object.keys(m)))

/**
 * Tech-Debt #8：按主题注入 :root 级 Aura text/content token（方案 B，P0 实证：Aura 默认
 * content token 固定 light 值 #334155，不随 data-p-theme / useTheme / updatePreset 切换）。
 *
 * 切换策略：
 * 1. 先 removeProperty 清理全部可能注入过的 token —— 回退到 Aura 默认样式表值。
 *    严禁 setProperty(k, '') 空字符串赋值：空串会使 var(--p-xxx) 解析失败。
 * 2. 再注入当前主题的映射（AURA_TOKEN_MAP[theme]）。
 *
 * // See RETAINED_CSS_OVERRIDES in aura-token-map.ts
 * 组件作用域直接值 token（DataTable 表头/正文、日历选中日）不在 :root，无法由此覆盖，
 * 需保留对应 CSS 覆盖（P3 去补丁化时以此为拆除/保留依据）。
 */
function syncAuraTextTokens(themeId: keyof typeof AURA_TOKEN_MAP) {
  const root = document.documentElement
  for (const token of ALL_MAPPED_TOKENS) root.style.removeProperty(token)
  const map = AURA_TOKEN_MAP[themeId] ?? {}
  for (const [token, value] of Object.entries(map)) root.style.setProperty(token, value)
}

/**
 * 在根组件 setup 中调用此函数，监听主题变化并同步到 PrimeVue。
 * 建议在 App.vue 中调用一次。
 *
 * PrimeVue 4.x 使用 Aura 主题时，通过 data-p-theme 属性控制明暗模式。
 * 同时通过 updateSurfacePalette() 将项目自定义主题的 surface 颜色注入 Aura 暗色色板，
 * 确保 dark/blue 主题的卡片背景色与项目设计 token 一致。
 * Tech-Debt #8：syncAuraTextTokens() 补充注入 text/content 系 token，解决深色主题下
 * Aura 组件文字（日历/表单/选项等）深字深底不可见问题。
 */
export function useThemeSync() {
  const store = useAppStore()

  watch(
    () => store.theme,
    (newTheme) => {
      const dark = isDarkTheme(newTheme)

      // PrimeVue 4.x 通过 data-p-theme 属性控制明暗模式
      if (dark) {
        document.documentElement.setAttribute('data-p-theme', 'dark')
      } else {
        document.documentElement.removeAttribute('data-p-theme')
      }

      // 无论明暗都同步 surface 色板，防止 updateSurfacePalette
      // 对 :root 层级全局令牌的修改在亮/暗模式间泄漏
      syncSurfacePalette(newTheme)
      // Tech-Debt #8：text/content token 随主题注入（先清理后注入，防残留）
      syncAuraTextTokens(newTheme)
    },
    { immediate: true },
  )
}
