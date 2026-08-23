// web/src/config/themes.ts — 四套主题完整配置
// 与 WinUI 端共享相同的配色体系

export interface ThemeConfig {
  id: string
  label: string
  type: 'light' | 'dark'
  // 完整色板（与 style.css / theme.css 的 CSS 变量一一对应）
  colors: {
    bg: string
    surface: string
    surfaceRaised: string
    border: string
    borderLight: string
    textDim: string
    // fix(a11y): 辅助文字色（用于表单 label/表头/次要按钮等），浅色主题下保证 ≥4.5:1；--text-dim 保留"极次要/禁用态"语义
    textSecondary: string
    text: string
    textBright: string
    textHeading: string
    primary: string
    primaryHover: string
    primaryBg: string
    primaryBorder: string
    success: string
    successBg: string
    danger: string
    dangerBg: string
    warning: string
    warningBg: string
    info: string
    infoBg: string
    // fix(a11y): 语义状态标签文字色（浅色主题用深色变体、深色主题用浅色变体），保证标签文字 ≥3:1
    successText: string
    warnText: string
    infoText: string
    dangerText: string
    selected: string
    focusRing: string
    shadowXs: string
    shadowSm: string
    shadow: string
    shadowMd: string
    shadowLg: string
    disabledBg: string
    disabledText: string
    // P0-2: MoviePilot 卡片变量（纳入动态注入）
    mpCardBg: string
    mpCardBorder: string
    mpCardDarkBg: string
    mpCardDarkBorder: string
    // P1-6: 主按钮阴影（四主题各自匹配主色发光值）
    buttonPrimaryShadow: string
  }
}

export const THEMES: Record<string, ThemeConfig> = {
  light: {
    id: 'light',
    label: '经典白',
    type: 'light',
    colors: {
      bg: '#f1f5f9',         // 降低亮度，从 #f8fafc 改为更柔和的灰蓝色
      surface: '#ffffff',
      surfaceRaised: '#f8fafc',
      border: '#e2e8f0',
      borderLight: '#f1f5f9',
      textDim: '#5f6f82',       // fix(theme): --text-dim 重设计（on --bg #f1f5f9 ≈ 4.69:1，保留弱化感；原 #64748b 实测仅 4.34）
      // fix(a11y): 实测辅助文字多落在 surface-raised(#f1f5f9) 上，#64748b 仅 4.34:1；#5b6b80 实测 4.96:1(on #f1f5f9)/5.44:1(on #ffffff)
      textSecondary: '#5b6b80',
      text: '#475569',
      textBright: '#334155',
      textHeading: '#0f172a',
      primary: '#6366f1',
      primaryHover: '#4f46e5',
      primaryBg: 'rgba(99, 102, 241, 0.1)',
      primaryBorder: 'rgba(99, 102, 241, 0.3)',
      success: '#22c55e',
      successBg: 'rgba(34, 197, 94, 0.12)',
      successText: '#065f46',   // 深绿 on 12%绿底 ≈ 6.9:1
      danger: '#ef4444',
      dangerBg: 'rgba(239, 68, 68, 0.12)',
      dangerText: '#991b1b',    // 深红 ≈ 7.2:1
      warning: '#f59e0b',
      warningBg: 'rgba(245, 158, 11, 0.12)',
      warnText: '#92400e',      // 深橙 ≈ 6.7:1
      info: '#3b82f6',
      infoBg: 'rgba(59, 130, 246, 0.12)',
      infoText: '#1e40af',      // 深蓝 ≈ 7.6:1
      selected: 'rgba(99, 102, 241, 0.08)',
      focusRing: '0 0 0 3px rgba(99, 102, 241, 0.25)',
      shadowXs: '0 1px 2px rgba(0, 0, 0, 0.05)',
      shadowSm: '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.05)',
      shadow: '0 4px 8px -4px rgba(0, 0, 0, 0.12), 0 2px 4px -2px rgba(0, 0, 0, 0.08)',
      shadowMd: '0 8px 16px -6px rgba(0, 0, 0, 0.15), 0 4px 8px -4px rgba(0, 0, 0, 0.1)',
      shadowLg: '0 16px 32px -12px rgba(0, 0, 0, 0.18)',
      disabledBg: '#e2e8f0',
      disabledText: '#94a3b8',
      mpCardBg: 'rgba(255, 255, 255, 0.7)',
      mpCardBorder: '1px solid rgba(0, 0, 0, 0.06)',
      mpCardDarkBg: 'rgba(15, 23, 42, 0.85)',
      mpCardDarkBorder: '1px solid rgba(255, 255, 255, 0.08)',
      buttonPrimaryShadow: '0 4px 14px rgba(99, 102, 241, 0.4)',
    },
  },
  dark: {
    id: 'dark',
    label: '暗夜黑',
    type: 'dark',
    colors: {
      bg: '#0f172a',
      surface: '#1e293b',
      surfaceRaised: '#334155',
      border: '#475569',
      borderLight: '#334155',
      textDim: '#a3afc2',       // fix(theme): --text-dim 重设计（on surface-raised #334155 ≈ 4.65:1；原 #94a3b8 实测仅 4.04）
      textSecondary: '#94a3b8',   // 浅色辅助文字 on 深色底
      text: '#cbd5e1',
      textBright: '#e2e8f0',
      textHeading: '#f1f5f9',
      primary: '#818cf8',
      primaryHover: '#6366f1',
      primaryBg: 'rgba(129, 140, 248, 0.15)',
      primaryBorder: 'rgba(129, 140, 248, 0.35)',
      success: '#4ade80',
      successBg: 'rgba(74, 222, 128, 0.15)',
      successText: '#4ade80',
      danger: '#f87171',
      dangerBg: 'rgba(248, 113, 113, 0.15)',
      dangerText: '#f87171',
      warning: '#fbbf24',
      warningBg: 'rgba(251, 191, 36, 0.15)',
      warnText: '#fbbf24',
      info: '#60a5fa',
      infoBg: 'rgba(96, 165, 250, 0.15)',
      infoText: '#60a5fa',      // 浅蓝
      selected: 'rgba(129, 140, 248, 0.12)',
      focusRing: '0 0 0 3px rgba(129, 140, 248, 0.3)',
      shadowXs: '0 1px 2px rgba(0, 0, 0, 0.3)',
      shadowSm: '0 1px 3px rgba(0, 0, 0, 0.4)',
      shadow: '0 4px 8px -4px rgba(0, 0, 0, 0.5)',
      shadowMd: '0 8px 16px -6px rgba(0, 0, 0, 0.6)',
      shadowLg: '0 16px 32px -12px rgba(0, 0, 0, 0.7)',
      disabledBg: '#475569',
      disabledText: '#94a3b8',
      mpCardBg: 'rgba(30, 41, 59, 0.85)',
      mpCardBorder: '1px solid rgba(255, 255, 255, 0.08)',
      mpCardDarkBg: 'rgba(15, 23, 42, 0.85)',
      mpCardDarkBorder: '1px solid rgba(255, 255, 255, 0.08)',
      buttonPrimaryShadow: '0 4px 14px rgba(129, 140, 248, 0.4)',
    },
  },
  green: {
    id: 'green',
    label: '护眼绿',
    type: 'light',
    colors: {
      bg: '#e8f5e9',         // 降低亮度，从 #f0fdf4 改为更柔和的浅绿色
      surface: '#f6fbf7',    // 从纯白改为极浅的绿色，降低刺眼感
      surfaceRaised: '#dcfce7',
      border: '#bbf7d0',
      borderLight: '#dcfce7',
      textDim: '#5f6f82',       // fix(theme): --text-dim 重设计（on --bg #e8f5e9 ≈ 4.55:1；原 #65a77d 仅 2.3:1、#64748b 实测 4.23）
      textSecondary: '#3d7a52',   // on #f6fbf7 ≈ 4.88:1 ✅
      text: '#166534',
      textBright: '#15803d',
      textHeading: '#14532d',
      primary: '#22c55e',
      primaryHover: '#16a34a',
      primaryBg: 'rgba(34, 197, 94, 0.1)',
      primaryBorder: 'rgba(34, 197, 94, 0.3)',
      success: '#16a34a',
      successBg: 'rgba(22, 163, 74, 0.12)',
      successText: '#065f46',   // 深绿（green 底色更暗，对比度更高）
      danger: '#ef4444',
      dangerBg: 'rgba(239, 68, 68, 0.12)',
      dangerText: '#991b1b',
      warning: '#f59e0b',
      warningBg: 'rgba(245, 158, 11, 0.12)',
      warnText: '#92400e',
      info: '#3b82f6',
      infoBg: 'rgba(59, 130, 246, 0.12)',
      infoText: '#1e40af',
      selected: 'rgba(34, 197, 94, 0.08)',
      focusRing: '0 0 0 3px rgba(34, 197, 94, 0.25)',
      shadowXs: '0 1px 2px rgba(0, 0, 0, 0.05)',
      shadowSm: '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.05)',
      shadow: '0 4px 8px -4px rgba(0, 0, 0, 0.12), 0 2px 4px -2px rgba(0, 0, 0, 0.08)',
      shadowMd: '0 8px 16px -6px rgba(0, 0, 0, 0.15), 0 4px 8px -4px rgba(0, 0, 0, 0.1)',
      shadowLg: '0 16px 32px -12px rgba(0, 0, 0, 0.18)',
      disabledBg: '#bbf7d0',
      disabledText: '#86efac',
      mpCardBg: 'rgba(246, 251, 247, 0.85)',
      mpCardBorder: '1px solid rgba(0, 0, 0, 0.06)',
      mpCardDarkBg: 'rgba(15, 23, 42, 0.85)',
      mpCardDarkBorder: '1px solid rgba(255, 255, 255, 0.08)',
      buttonPrimaryShadow: '0 4px 14px rgba(34, 197, 94, 0.4)',
    },
  },
  blue: {
    id: 'blue',
    label: '科技蓝',
    type: 'dark',
    colors: {
      bg: '#0c1222',
      surface: '#151e32',
      surfaceRaised: '#1e293b',
      border: '#1e293b',
      borderLight: '#1e293b',
      textDim: '#a3afc2',       // fix(theme): --text-dim 重设计（on surface-raised ≈ 4.65:1）
      textSecondary: '#94a3b8',   // 浅色辅助文字 on 深蓝底
      text: '#cbd5e1',
      textBright: '#e2e8f0',
      textHeading: '#f1f5f9',
      primary: '#0ea5e9',
      primaryHover: '#0284c7',
      primaryBg: 'rgba(14, 165, 233, 0.15)',
      primaryBorder: 'rgba(14, 165, 233, 0.35)',
      success: '#4ade80',
      successBg: 'rgba(74, 222, 128, 0.15)',
      successText: '#4ade80',
      danger: '#f87171',
      dangerBg: 'rgba(248, 113, 113, 0.15)',
      dangerText: '#f87171',
      warning: '#fbbf24',
      warningBg: 'rgba(251, 191, 36, 0.15)',
      warnText: '#fbbf24',
      info: '#60a5fa',
      infoBg: 'rgba(96, 165, 250, 0.15)',
      infoText: '#60a5fa',      // 浅蓝 on 深蓝底
      selected: 'rgba(14, 165, 233, 0.12)',
      focusRing: '0 0 0 3px rgba(14, 165, 233, 0.3)',
      shadowXs: '0 1px 2px rgba(0, 0, 0, 0.3)',
      shadowSm: '0 1px 3px rgba(0, 0, 0, 0.4)',
      shadow: '0 4px 8px -4px rgba(0, 0, 0, 0.5)',
      shadowMd: '0 8px 16px -6px rgba(0, 0, 0, 0.6)',
      shadowLg: '0 16px 32px -12px rgba(0, 0, 0, 0.7)',
      disabledBg: '#1e293b',
      disabledText: '#475569',
      mpCardBg: 'rgba(21, 30, 50, 0.85)',
      mpCardBorder: '1px solid rgba(255, 255, 255, 0.08)',
      mpCardDarkBg: 'rgba(15, 23, 42, 0.85)',
      mpCardDarkBorder: '1px solid rgba(255, 255, 255, 0.08)',
      buttonPrimaryShadow: '0 4px 14px rgba(14, 165, 233, 0.4)',
    },
  },
}

/** 暗色主题 ID 集合 */
export const DARK_THEME_IDS = new Set(['dark', 'blue'])

/** 根据主题 ID 判断是否为暗色主题 */
export function isDarkTheme(themeId: string): boolean {
  return DARK_THEME_IDS.has(themeId)
}

/** 将主题配置应用到 DOM（CSS 变量 + data-theme 属性） */
export function applyThemeToDom(theme: ThemeConfig): void {
  const root = document.documentElement
  const c = theme.colors

  // 设置 data-theme 属性（用于 CSS 选择器）
  root.setAttribute('data-theme', theme.id)

  // 应用 CSS 变量
  const vars: Record<string, string> = {
    '--bg': c.bg,
    '--surface': c.surface,
    '--surface-raised': c.surfaceRaised,
    '--border': c.border,
    '--border-light': c.borderLight,
    '--text-dim': c.textDim,
    '--text-secondary': c.textSecondary,
    '--text': c.text,
    '--text-bright': c.textBright,
    '--text-heading': c.textHeading,
    '--primary': c.primary,
    '--primary-hover': c.primaryHover,
    '--primary-bg': c.primaryBg,
    '--primary-border': c.primaryBorder,
    '--success': c.success,
    '--success-bg': c.successBg,
    '--success-text': c.successText,
    '--danger': c.danger,
    '--danger-bg': c.dangerBg,
    '--danger-text': c.dangerText,
    '--warning': c.warning,
    '--warning-bg': c.warningBg,
    '--warn-text': c.warnText,
    '--info': c.info,
    '--info-bg': c.infoBg,
    '--info-text': c.infoText,
    '--selected': c.selected,
    '--focus-ring': c.focusRing,
    '--shadow-xs': c.shadowXs,
    '--shadow-sm': c.shadowSm,
    '--shadow': c.shadow,
    '--shadow-md': c.shadowMd,
    '--shadow-lg': c.shadowLg,
    // P0-2: MoviePilot 卡片变量
    '--mp-card-bg': c.mpCardBg,
    '--mp-card-border': c.mpCardBorder,
    '--mp-card-dark-bg': c.mpCardDarkBg,
    '--mp-card-dark-border': c.mpCardDarkBorder,
    // P1-6: 主按钮阴影
    '--button-primary-shadow': c.buttonPrimaryShadow,
    // 向后兼容别名
    '--accent': c.primary,
    '--accent-dim': c.primaryHover,
    '--accent-bg': c.primaryBg,
    '--accent-border': c.primaryBorder,
  }

  for (const [key, value] of Object.entries(vars)) {
    root.style.setProperty(key, value)
  }
}
