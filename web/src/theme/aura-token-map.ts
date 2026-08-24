// web/src/theme/aura-token-map.ts
// Tech-Debt #8 P1：项目主题 → Aura text/content token 映射表（做减法原则）
//
// P0 结论：Aura 的 text/content 系 token 固定为 light 值（--p-content-color 恒为 #334155），
// 不随 data-p-theme / useTheme / updatePreset 变化（验证环境实证，见 docs/investigations/aura-token-sync-feasibility.md）。
// 方案 B：在 useThemeSync 中按主题 setProperty 注入 :root 级 token（与 updateSurfacePalette 同路径，P2 实施）。
//
// 做减法原则（P1 审核指导）：
//   1. 优先根节点 token（--p-content-color 等）；不逐组件映射
//   2. light/green 的 content 系保持 Aura 默认（#334155 实测达标），仅注入按钮/选中日等不达标项
//   3. 组件作用域直接值 token（DataTable 表头/正文等，见下）不在 :root，注入无效 → 保留 CSS 覆盖

import type { ThemeId } from '@/stores/app'

export interface AuraTokenMap {
  /** Aura CSS 变量名（:root 级）→ 注入值 */
  [token: string]: string
}

/**
 * 四主题 → :root 级 Aura token 注入映射
 *
 * 消费者标注（P3 去补丁化"拆除指南"）：
 * - 注入某 token 后，可移除其消费者组件上的临时 CSS 覆盖
 * - 未列入的组件作用域 token 需保留 CSS 覆盖（见 RETAINED_CSS_OVERRIDES）
 */
export const AURA_TOKEN_MAP: Record<ThemeId, AuraTokenMap> = {
  light: {
    // hotfix(tech-debt#8): 显式注入，不依赖 Aura 默认值——实测部分环境 data-p-theme="dark" 残留时
    // Aura dark token 生效使 --p-content-color 解析为 #ffffff（dark surface.0），内联注入可免疫。
    // 消费者：全站未显式设色文本、DatePicker(header/weekday/day)、Card、Dialog、Toast 正文
    '--p-content-color': '#334155',
    '--p-content-hover-color': '#1e293b',
    '--p-text-color': '#334155',
    '--p-text-hover-color': '#1e293b',
    // 消费者：辅助文字、placeholder
    '--p-text-muted-color': '#64748b',
    // 消费者：InputText/Textarea/Dropdown 表单文字
    '--p-form-field-color': '#334155',
    '--p-form-field-placeholder-color': '#64748b',
    // 消费者：Select/Dropdown 选项
    '--p-list-option-color': '#334155',
    '--p-list-option-focus-color': '#1e293b',
    // 消费者：Primary 按钮（全站主操作）——品牌 indigo-600 + 白字（6.29:1）
    '--p-button-primary-background': '#4f46e5',
    '--p-button-primary-color': '#ffffff',
    '--p-button-primary-hover-background': '#4338ca',
    '--p-button-primary-hover-color': '#ffffff',
    '--p-button-primary-active-background': '#4338ca',
    '--p-button-primary-active-color': '#ffffff',
  },
  green: {
    // hotfix(tech-debt#8)：同上，显式注入（green 为浅色主题，深色文字）
    '--p-content-color': '#334155',
    '--p-content-hover-color': '#1e293b',
    '--p-text-color': '#334155',
    '--p-text-hover-color': '#1e293b',
    '--p-text-muted-color': '#64748b',
    '--p-form-field-color': '#334155',
    '--p-form-field-placeholder-color': '#64748b',
    '--p-list-option-color': '#334155',
    '--p-list-option-focus-color': '#1e293b',
    // 消费者：Primary 按钮——green 主色 #22c55e + 黑字（9.2:1，白字 2.5:1 不达标）
    '--p-button-primary-background': '#22c55e',
    '--p-button-primary-color': '#000000',
    '--p-button-primary-hover-background': '#16a34a',
    '--p-button-primary-hover-color': '#000000',
    '--p-button-primary-active-background': '#16a34a',
    '--p-button-primary-active-color': '#000000',
  },
  blue: {
    // 消费者：全站未显式设色文本、DatePicker(header/weekday/day/selectMonth/year)、Card、Dialog、Toast 正文
    '--p-content-color': '#e2e8f0',
    '--p-content-hover-color': '#cbd5e1',
    '--p-text-color': '#e2e8f0',
    '--p-text-hover-color': '#cbd5e1',
    // 消费者：辅助文字、placeholder、list optionGroup 标题
    '--p-text-muted-color': '#94a3b8',
    // 消费者：InputText/Textarea/Dropdown 表单文字（Aura light 值 #334155 on 深色字段底不可读）
    '--p-form-field-color': '#e2e8f0',
    '--p-form-field-placeholder-color': '#94a3b8',
    // 消费者：Select/Dropdown 选项（--p-list-option-color 为 :root 级，实测可注入）
    '--p-list-option-color': '#e2e8f0',
    '--p-list-option-focus-color': '#cbd5e1',
    // 消费者：Primary 按钮（品牌 sky-500 + 黑字 7.6:1）
    '--p-button-primary-background': '#0ea5e9',
    '--p-button-primary-color': '#000000',
    '--p-button-primary-hover-background': '#0284c7',
    '--p-button-primary-hover-color': '#000000',
    '--p-button-primary-active-background': '#0284c7',
    '--p-button-primary-active-color': '#000000',
  },
  dark: {
    // 消费者：同 blue（--primary #818cf8 indigo-400 + 黑字 7.0:1）
    '--p-content-color': '#e2e8f0',
    '--p-content-hover-color': '#cbd5e1',
    '--p-text-color': '#e2e8f0',
    '--p-text-hover-color': '#cbd5e1',
    '--p-text-muted-color': '#94a3b8',
    '--p-form-field-color': '#e2e8f0',
    '--p-form-field-placeholder-color': '#94a3b8',
    '--p-list-option-color': '#e2e8f0',
    '--p-list-option-focus-color': '#cbd5e1',
    '--p-button-primary-background': '#818cf8',
    '--p-button-primary-color': '#000000',
    '--p-button-primary-hover-background': '#6366f1',
    '--p-button-primary-hover-color': '#000000',
    '--p-button-primary-active-background': '#6366f1',
    '--p-button-primary-active-color': '#000000',
  },
}

/**
 * --text-dim 重设计映射（fix(theme) 第二轨 + 批次5-E组 v2）：
 * 审计发现原方案值 on 实际背景不达标（light/green #64748b on --bg #f1f5f9 仅 4.34、
 * dark/blue #94a3b8 on surface-raised #334155 仅 4.04），已调优 v1：light/green #5f6f82、
 * dark/blue #a3afc2；批次5-E组 v2：light/green #445264（语义梯度 ΔL*(sec→dim)≥10 且
 * on --bg ≥4.5:1，原 #5f6f82 与 --text-secondary 亮度差仅 1.5 不满足梯度）。
 * 由 syncAuraTextTokens 注入 --text-dim（与 themes.ts applyThemeToDom 值一致，双保险）。
 */
export const AURA_TEXT_DIM_MAP: Record<ThemeId, string> = {
  light: '#445264',
  dark: '#a3afc2',
  green: '#445264',
  blue: '#a3afc2',
}

/**
 * 保留的 CSS 覆盖清单（P3 决策依据：功能需求/组件作用域 token 限制，非缺陷补丁）
 *
 * 1. DataTable 表头/正文文字（style.css .p-datatable .p-datatable-thead>tr>th 与 tbody td）：
 *    Aura 组件作用域 token（--p-datatable-header-cell-color 等）为**解析后直接值**（#334155），
 *    不在 :root，根注入无效（实测）；保留覆盖以维持四主题达标。
 * 2. 日历选中日（.p-datepicker-day-selected）：
 *    Aura 默认 emerald-500+白字 2.54:1 不达标；选中日背景 token 为组件作用域，
 *    注入成本高，保留 CSS 覆盖（#047857+白字 5.48:1）。
 */
export const RETAINED_CSS_OVERRIDES: ReadonlyArray<{ selector: string; reason: string }> = [
  {
    selector: '.p-datatable .p-datatable-thead>tr>th, .p-datatable .p-datatable-tbody>tr>td',
    reason: '组件作用域直接值 token（--p-datatable-* 不在 :root），根注入无效；四主题覆盖维持达标',
  },
  {
    selector: '.p-datepicker-panel .p-datepicker-day-selected',
    reason: 'Aura 默认选中日 2.54:1 不达标；选中日 token 为组件作用域，保留 #047857+白字覆盖',
  },
]
