# 设计令牌审计报告（Design Token Audit）

> **任务**：前端视觉资产审计与设计令牌治理 · 阶段二
> **分支**：`chore/design-tokens` ｜ **基线**：`main@ee74e83c`
> **首次生成**：2026-11-21 ｜ **扫描根**：`web/src`（66 个 `.vue`/`.css`）
> **生成来源**：`python scripts/audit_design_tokens.py`。§4 为自动生成区块（标记 `AUDIT-BEGIN` / `AUDIT-END`，脚本按标记刷新），改动代码后重跑即刷新；§0–§3、§5–§11 为人工撰写。
>
> **基线说明**：预检时 `main` 为 `561806c9`，暂停期间仓库前进到 `ee74e83c`（新增 A-46 判定单测等），本分支从**当前** `main` 切出；`pnpm test` 用例数因此从 412 变为 415，与本次改动无关。

## 0. 摘要

| 结论 | 数值 / 判断 |
|---|---|
| **当前状态（全量替换后）** | 命中 **709** 条：**A 0** / B 150 / C 559 / D 0（P5-4 `100%`、P5-5 `vh/fr` 计入 B 类）（A-51 消除 3 条；P5-1 新增 `--text-on-primary` 后 B 再减 6 条） |
| 阶段二审计快照（替换前） | 命中 1722 条：A 979 / B 115 / C 628 / D 0（历史快照，保留原值）（不含已令牌化声明 859 条、与视觉无关的声明 1095 条） |
| A 精确映射 | **979 条已全部替换**（试点 17 + 5-1 118 + 5-2 204 + 5-3 272 + 5-4 333 + 5-5 35），见 §7 |
| B 近似映射 | **115 条保持字面量** = **113 条带 `TODO: [Design Debt]`**（5 批 112 + 试点 1）+ **2 条内联白名单**（`PendingView:90 height:20px`、`SystemResources:49 height:24px`，HTML 属性无法插 CSS 注释）。全树 TODO 文本共 **114 处** = 113（B 行）+ 1（旧圆角别名 `10px → var(--radius)`，对应一条已替换的 A 行） |
| C 排除 | **627** 条 —— 令牌定义、`var()` fallback、PrimeVue 覆盖白名单、SVG 图表、布局尺寸等（理由见 §4.2） |
| D 缺陷 | **0** 条 —— 修复前为 11 个未定义变量 / 26 处引用（D1），已清零并由测试守护 |
| 涉及文件 | 60 / 66（`styles/design-tokens.css` 与 `theme.css` 无命中） |
| 试点组件 | **`components/NotificationBell.vue`**（18 条：A 17 已替换 / B 1 留 TODO） |

**核心判断**：本仓的颜色令牌层已经存在且质量不低（四主题 + a11y 契约测试），真正缺的是**与主题无关的尺度层**（间距/字号/字重/行高/圆角/尺寸）和**引用完整性门禁**。因此本报告的主战场是尺度类硬编码——阶段二的 A 类 979 条按属性分布为：`font-size` 309、`gap` 180、`margin` 175、`padding` 168、`font-weight` 110，五项合计 942（96%），颜色类仅占 33 条。**全量替换完成后，剩余的 115 条 B 类才是真正的"无令牌可映射"项**，它们构成 G-055 门禁基线的主体。

---

## 1. 范围与方法

| 项 | 说明 |
|---|---|
| 扫描根 | `web/src`（仓库根无 `src/`，任务包默认假设 1 已修订） |
| 文件类型 | `.vue`（62）、`.css`（4）；`.vue` 只解析 `<style>` 块与 `style=""` 内联样式，不解析 `:style` JS 绑定 |
| 排除 | `node_modules`、`dist`、`e2e`、`*.test.ts`、`eslint-plugin-custom` |
| 注释处理 | 扫描前把 `/* ... */` 替换为等长空白（保留行号），避免注释里的色值/E0X 示例被误判 |
| 行号 | 相对源文件真实行号（`<style>` 块按块起始行偏移换算） |
| 可重跑 | `python scripts/audit_design_tokens.py --check`（只统计）/ 无参数（刷新本文件 §4） |

**为什么需要脚本**：审计要求"文件 | 行号 | 原值 | 建议令牌"逐行可复核，而全站 46 万字节的 `.vue`/`.css` 靠人工列不全；脚本还能保证阶段五批量替换时的输入与审计同源（同一套分类函数）。

---

## 2. 分类口径（A / B / C / D）

| 类 | 含义 | 处置 | 置信度 |
|---|---|---|---|
| **A** | 值精确命中已定义令牌（如 `13px → --font-size-13`、`8px → --space-8`、`#ef4444 → --danger`） | 阶段三/五机械替换，不改变视觉 | 高（少数按值精确匹配的为"中"） |
| **B** | 无精确令牌（如 `#e74c3c`、`height: 60px`、`#fff` 作为前景色） | **必须先人工确认**；确定映射后就近替换 + 行上方 `TODO: [Design Debt]` | 中/低 |
| **C** | 不纳入替换：令牌定义、`var()` fallback、PrimeVue `RETAINED` 覆盖、SVG 图表、布局尺寸/百分比/`calc`、装饰细线 | 不动，登记为门禁基线例外 | — |
| **D** | `var()` 引用了未定义变量（真缺陷，非样式债） | 直接修，不进基线（修复前 26 处，现 0） | — |

**判定顺序**：D（未定义引用）→ C（令牌定义 / 已用令牌 / 计算值 / 组件与文件级排除）→ A/B（按属性族映射）。顺序不可调换：否则 `var(--x, #fff)` 会被误判成颜色硬编码。

---

## 3. 令牌现状：四层结构（本轮新增第 0 层）

| 层 | 文件 | 内容 | 是否随主题变化 |
|---|---|---|---|
| **0 尺度层（新）** | `web/src/styles/design-tokens.css` | **63 个令牌**：间距 19 / 字号 16 / 字号语义别名 7 / 行高 7 / 字重 5 / 圆角 6 / 图标方块 2 / 按钮高度 1 | 否（主题无关） |
| 1 默认层 | `web/src/style.css` `:root` | 56 个 CSS 变量（颜色/阴影/圆角/字体/侧栏宽度） | 是（JS 注入后覆盖） |
| 2 运行层 | `web/src/config/themes.ts` `applyThemeToDom()` | 44 个变量 × 4 主题（light/dark/green/blue），色板 45 键 | 是（唯一可切换真相） |
| 3 桥接层 | `web/src/theme/aura-token-map.ts` | PrimeVue Aura `:root` 级 `--p-*` 注入（81 个色值）+ `RETAINED_CSS_OVERRIDES` 白名单 | 是 |

**单一真相规则（本报告与后续门禁共同遵守）**：

1. **颜色只能定义在 1/2/3 层**，组件与 `design-tokens.css` 内不得出现颜色字面量；
2. **尺度只能定义在 0 层**，组件内不得出现 `font-size: Npx` / `padding: Npx` / `border-radius: Npx` 等字面量（C 类例外除外）；
3. `var()` 引用的名字必须存在于上述集合（`--p-*` 由 PrimeVue 提供，豁免），由 `web/src/styles/design-tokens.test.ts` 守护；
4. 改颜色令牌必须同时跑 `theme-spec.test.ts`（30 例）与 `a11y-contrast.test.ts`（7 例）。

---


## 4. 审计明细与汇总统计（自动生成）

<!-- AUDIT:BEGIN -->
### 4.1 可替换明细（A 精确映射 / B 近似映射）

共 **115** 条（A 0 / B 115）。

| 文件路径 | 行号 | 当前硬编码值 | 样式属性 | 建议令牌 | 匹配置信度 | 备注 |
|---|---|---|---|---|---|---|
| components/AppHeader.vue | 107 | 60px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppHeader.vue | 110 | rgba(255, 255, 255, 0.8) | background | （无） | 低 | 无对应语义令牌 |
| components/AppHeader.vue | 115 | 0 1px 3px rgba(0, 0, 0, 0.05), 0 4px 12px -4px rgba(0, 0, 0, 0.08) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppHeader.vue | 126 | rgba(30, 41, 59, 0.85) | background | （无） | 低 | 无对应语义令牌 |
| components/AppHeader.vue | 230 | 56px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppHeader.vue | 247 | 40px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 190 | 72px | padding-bottom | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 209 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 211 | 32px 36px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 236 | 68px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 239 | env(safe-area-inset-bottom) | padding-bottom | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 241 | rgba(255, 255, 255, 0.9) | background | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 245 | 1px solid rgba(226, 232, 240, 0.5) | border-top | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 247 | 0 -2px 16px rgba(0, 0, 0, 0.06) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppLayout.vue | 254 | rgba(15, 23, 42, 0.9) | background | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 256 | rgba(51, 65, 85, 0.5) | border-top-color | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 284 | 0 0 3px 3px | border-radius | （无） | 中 | 非令牌圆角档位 |
| components/AppLayout.vue | 318 | 64px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 347 | 56px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 354 | #ffffff | color | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 360 | 0 4px 12px rgba(0, 0, 0, 0.15) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppLayout.vue | 372 | 0 6px 16px rgba(0, 0, 0, 0.2) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppSidebar.vue | 78 | 2px 0 8px rgba(0, 0, 0, 0.03) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppSidebar.vue | 146 | 0 2px 8px rgba(99, 102, 241, 0.08) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppSidebar.vue | 157 | 24px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppSidebar.vue | 160 | 0 4px 4px 0 | border-radius | （无） | 中 | 非令牌圆角档位 |
| components/AppSidebar.vue | 162 | 2px 0 8px rgba(99, 102, 241, 0.3) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/LogBar.vue | 225 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/LogBar.vue | 243 | #555 | background | （无） | 低 | 无对应语义令牌 |
| components/LogBar.vue | 249 | 4px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/NotificationBell.vue | 218 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/RouteDebugPanel.vue | 144 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/TableLoadFooter.vue | 69 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/TableLoadFooter.vue | 73 | #ca8a04 | color | （无） | 低 | 无对应语义令牌 |
| components/TableLoadFooter.vue | 77 | 20px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/UnifiedFilterBar.vue | 87 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/ValidityConfig.vue | 445 | 36px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/ValidityConfig.vue | 447 | 36px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/ValidityConfig.vue | 479 | bold | font-weight | （无） | 低 | 非常规字重 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 162 | rgba(239,68,68,0.25) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 162 | rgba(239,68,68,0.04) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 165 | rgba(245,158,11,0.25) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 165 | rgba(245,158,11,0.04) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 169 | 36px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 184 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 153 | rgba(59,130,246,0.3) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 153 | rgba(59,130,246,0.04) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 156 | rgba(239,68,68,0.2) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 156 | rgba(239,68,68,0.03) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 159 | rgba(245,158,11,0.2) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 159 | rgba(245,158,11,0.03) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 182 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 190 | rgba(239,68,68,0.85) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 193 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/QuickActionsCard.vue | 143 | rgba(139,92,246,0.12) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/QuickActionsCard.vue | 145 | #8b5cf6 | color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/StatsCard.vue | 83 | linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08)) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/StatsCard.vue | 85 | 1px solid rgba(99,102,241,0.25) | border | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/StatsCard.vue | 96 | 100px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/SystemInfoCard.vue | 94 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/SystemLogCard.vue | 114 | rgba(0,0,0,0.08) | background | （无） | 低 | 无对应语义令牌 |
| style.css | 126 | rgba(99, 102, 241, 0.2) | border-color | （无） | 低 | 无对应语义令牌 |
| style.css | 140 | rgba(99, 102, 241, 0.04) | background | （无） | 低 | 无对应语义令牌 |
| style.css | 143 | 0 0 4px rgba(34,197,94,0.4) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| style.css | 145 | 0 0 14px rgba(34,197,94,0.7) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| style.css | 148 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| style.css | 150 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| style.css | 152 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| style.css | 757 | 0 2px 2px 0 | border-radius | （无） | 中 | 非令牌圆角档位 |
| style.css | 798 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/AnnounceDetail.vue | 255 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 270 | bold | font-weight | （无） | 低 | 非常规字重 |
| views/AnnounceDetail.vue | 274 | 0.5rem 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 280 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 295 | 0.5em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 314 | 0.25em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 325 | 0.25em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 336 | 0.25em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 348 | 0.25rem 0.5rem | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/DownloadImport.vue | 210 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/FavoritesView.vue | 182 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/ForbiddenView.vue | 28 | 12vh auto 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/HomeView.vue | 84 | 22px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/HomeView.vue | 84 | rgba(239,68,68,0.85) | background | （无） | 低 | 无对应语义令牌 |
| views/HomeView.vue | 84 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/LoginView.vue | 69 | linear-gradient(135deg, #667eea 0%, #764ba2 100%) | background | （无） | 低 | 无对应语义令牌 |
| views/LoginView.vue | 71 | 44px 36px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/NotificationLogsView.vue | 236 | 400px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/NotificationLogsView.vue | 262 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/NotificationLogsView.vue | 285 | 4px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/OrganizeView.vue | 199 | 9px 13px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/PendingView.vue | 90 | 20px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/RegisterView.vue | 66 | linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%) | background | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 70 | rgba(255,255,255,0.06) | background | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 72 | 1px solid rgba(255,255,255,0.1) | border | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 77 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 79 | rgba(255,255,255,0.5) | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 82 | 1px solid rgba(255,255,255,0.1) | border | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 85 | rgba(255,255,255,0.05) | background | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 85 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 89 | rgba(255,255,255,0.3) | color | （无） | 低 | 无对应语义令牌 |
| views/SettingsView.vue | 443 | #ffffff | color | （无） | 低 | 无对应语义令牌 |
| views/SettingsView.vue | 446 | 0 2px 8px rgba(99, 102, 241, 0.25) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| views/SystemResources.vue | 49 | 24px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/TaskView.vue | 483 | 9px 13px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/TaskView.vue | 508 | rgba(239,68,68,0.06) | background | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 520 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 522 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 524 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/settings/SettingsTabSites.vue | 324 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 109 | 12px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 167 | 44px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 185 | 12px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 191 | 0 2px 4px rgba(0, 0, 0, 0.2) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| views/settings/shared.css | 259 | inset 0 2px 4px rgba(0, 0, 0, 0.05) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |

### 4.2 排除明细（C：不纳入替换）

| 排除理由 | 条数 |
|---|---|
| 无字面量/布局值 | 228 |
| 布局尺寸（不纳入令牌） | 118 |
| PrimeVue 组件覆盖（RETAINED 已批准例外） | 93 |
| 相对单位布局值 | 53 |
| SVG 图表组件（几何/配色与数据绑定，整体排除） | 43 |
| var() fallback（随令牌变化，不改） | 28 |
| 计算值（布局，不纳入令牌） | 14 |
| 圆形（装饰性） | 13 |
| 装饰细线圆角（滚动条/进度条） | 9 |
| 滤镜效果（非令牌值） | 8 |
| 分隔细线高度 | 8 |
| 默认令牌层定义 | 7 |
| 百分比尺寸（布局） | 6 |

### 4.3 缺陷明细（D：未定义变量引用）

无。修复后 `web/src` 内 `var()` 引用未定义变量为 **0**（由 `web/src/styles/design-tokens.test.ts` 守护）。

### 4.4 总量

| 指标 | 数值 |
|---|---|
| 涉及文件（有命中） | 59 |
| 命中总数 | 743 |
| 已令牌化声明（不计入明细） | 1838 |
| 与视觉令牌无关（布局属性等） | 1095 |
| A 精确映射 | 0 |
| B 近似映射（需 TODO） | 115 |
| C 排除 | 627 |
| D 缺陷 | 0 |

### 4.5 按属性分类

| 属性 | A | B | 合计 |
|---|---|---|---|
| height | 0 | 32 | 32 |
| background | 0 | 21 | 21 |
| color | 0 | 16 | 16 |
| box-shadow | 0 | 12 | 12 |
| margin | 0 | 11 | 11 |
| border | 0 | 11 | 11 |
| padding | 0 | 7 | 7 |
| border-radius | 0 | 3 | 3 |
| font-weight | 0 | 2 | 2 |

### 4.6 无对应令牌的颜色字面量（B 类）

| 字面量 | 出现次数 |
|---|---|
| `#fff` | 10 |
| `#ffffff` | 2 |
| `rgba(239,68,68,0.85)` | 2 |
| `1px solid rgba(255,255,255,0.1)` | 2 |
| `rgba(255, 255, 255, 0.8)` | 1 |
| `rgba(30, 41, 59, 0.85)` | 1 |
| `rgba(255, 255, 255, 0.9)` | 1 |
| `1px solid rgba(226, 232, 240, 0.5)` | 1 |
| `rgba(15, 23, 42, 0.9)` | 1 |
| `rgba(51, 65, 85, 0.5)` | 1 |
| `rgba(239,68,68,0.25)` | 1 |
| `rgba(239,68,68,0.04)` | 1 |
| `rgba(245,158,11,0.25)` | 1 |
| `rgba(245,158,11,0.04)` | 1 |
| `rgba(59,130,246,0.3)` | 1 |
| `rgba(59,130,246,0.04)` | 1 |
| `rgba(239,68,68,0.2)` | 1 |
| `rgba(239,68,68,0.03)` | 1 |
| `rgba(245,158,11,0.2)` | 1 |
| `rgba(245,158,11,0.03)` | 1 |
| `rgba(139,92,246,0.12)` | 1 |
| `#8b5cf6` | 1 |
| `linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08))` | 1 |
| `1px solid rgba(99,102,241,0.25)` | 1 |
| `rgba(0,0,0,0.08)` | 1 |

### 4.7 文件维度 Top 10（A+B）

| 文件 | 条数 |
|---|---|
| components/AppLayout.vue | 16 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 9 |
| style.css | 9 |
| views/AnnounceDetail.vue | 9 |
| views/RegisterView.vue | 9 |
| components/AppHeader.vue | 6 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 6 |
| components/AppSidebar.vue | 5 |
| views/TaskView.vue | 5 |
| views/settings/shared.css | 5 |

<!-- AUDIT:END -->

## 5. Q2 颜色对照表（零 churn：沿用现有命名）

> 任务包的 `--color-*` 术语**不落地为新变量**，只作为本表的左列对照。理由：现有 `--bg/--text/--danger` 已被 4 套主题、37 个契约测试与约 200 处组件引用使用，改名收益为零、回归面巨大。

| 任务包术语 | 实际变量 | 当前值（light） | 是否已定义 | 备注 |
|---|---|---|---|---|
| `--color-bg-primary` | `--bg` | `#f1f5f9` | ✅ | 页面画布色；与 `--surface` 区分（见 ui-components.md §Token 语义基线） |
| `--color-text-primary` | `--text` | `#475569` | ✅ | 正文主色 |
| `--color-text-secondary` | `--text-secondary` | `#5b6b80` | ✅ | 辅助文字；`--text-dim` 为更弱一档 |
| `--color-border-default` | `--border` | `#e2e8f0` | ✅ | 另有 `--border-light` |
| `--color-state-success` | `--success` | `#22c55e` | ✅ | 语义背景用 `--success-bg`，文字用 `--success-text` |
| `--color-state-warning` | `--warning` | `#f59e0b` | ✅ | 文字用 `--warn-text`（注意旧拼写 `--warn` 已删除，见 §5.2） |
| `--color-state-error` | `--danger` | `#ef4444` | ✅ | **命名差异：error → danger** |
| `--color-brand-primary` | `--primary` | `#5c5ef2` | ✅ | 强调文字/描边；实心底用 `--primary-fill` |
| （任务包未列，实测缺口）`--color-on-primary` | **无** | — | ❌ | 主色底上的白字目前是字面量 `#fff`（B 类 12 处）；建议后续补语义令牌 |
| `--btn-height-md` | `--btn-height-md` | `34px` | ✅ | 见 §8 的语义偏差说明 |
| `--btn-height-lg` / `--btn-height-sm` | **无** | — | ❌ | 存量无消费者，按 Q1 锁定不引入未使用令牌 |
| `--radius-sm` / `--radius-md` | `--ds-radius-sm` / `--ds-radius-md` | `6px` / `8px` | ✅ | 旧 `--radius-sm(6px)` 仍在用，见 §6 |
| `--font-size-h1` … `--font-size-caption` | `--font-size-h1/h2/h3/h4/body/caption/micro` | `22/17/15/13/14/12/11px` | ✅ | 另有 16 档数字基座（`--font-size-9` … `--font-size-72`） |
| `--font-weight-regular/medium/bold` | `--font-weight-*` | `400/500/700` | ✅ | 另含 `--font-weight-semibold(600)` / `--font-weight-extrabold(800)` |
| `--line-height-*` | `--line-height-none/snug/compact/normal/body/relaxed/loose` | `1/1.25/1.3/1.5/1.6/1.7/1.8` | ✅ | 取自实测 7 档 |
| `--spacing-4` 等 | `--space-1/2/3/4/6/7/8/9/10/12/14/16/18/20/24/30/32/40/44` | 同值 | ✅ | 实测 19 档，off-grid 档标注待收敛 |

### 5.1 任务包术语与实际变量的命名差异（必须记住的三处）

1. **`error` 在仓内叫 `danger`** —— 新代码请用 `--danger` / `--danger-bg` / `--danger-text`；
2. **警告文字色是 `--warn-text`（不是 `--warning-text`）**，且**没有** `--warn` 这个变量（D3 曾是拼写错误）；
3. **`--primary` 只做前景**（文字/图标/描边），**实心底用 `--primary-fill`** —— 两者拆开是为了同时满足"深底浅字"与"浅底白字"两种对比度要求。

### 5.2 D1 / D3 的 11 个未定义变量处置（已全部修复）

| 原变量名 | 引用数 | 处置 | 现用令牌 |
|---|---|---|---|
| `--surface-card` | 1 | 改名 | `--surface` |
| `--surface-border` | 1 | 改名 | `--border` |
| `--surface-hover` | 2 | 语义替换 | `--selected` |
| `--primary-50` | 1 | 语义替换 | `--primary-bg` |
| `--primary-color` | 4 | 改名 | `--primary` |
| `--text-color` | 1 | 改名 | `--text` |
| `--text-color-secondary` | 12 | 改名 | `--text-secondary` |
| `--green-500` | 1 | 语义替换 | `--success` |
| `--red-500` | 1 | 语义替换 | `--danger` |
| `--gray-400` | 1 | 就近映射 | `--text-dim`（浅色下更深，已登记视觉影响） |
| `--warn`（拼写错误） | 1 | 正名 | `--warning` |

---

## 6. Q1 圆角映射表（旧变量 ↔ 新令牌）

| 旧变量（保留，不删） | 值 | 新令牌 | 值 | 关系 |
|---|---|---|---|---|
| `--radius-sm` | 6px | `--ds-radius-sm` | 6px | **同值**，旧名继续被现有规则使用 |
| `--radius` | 10px | （无同值新令牌） | — | 旧名保留；10px 字面量替换时**直接用 `var(--radius)`** |
| `--radius-lg` | 14px | `--ds-radius-xl` | 16px | **不同值**，不可互换 |
| — | 4px | `--ds-radius-xs` | 4px | 新增（实测 5 处） |
| — | 8px | `--ds-radius-md` | 8px | 新增 |
| — | 12px | `--ds-radius-lg` | 12px | 新增 |
| — | 16px | `--ds-radius-xl` | 16px | 新增 |
| — | 999px | `--ds-radius-pill` | 999px | 新增（胶囊） |

> ⚠️ **命名陷阱（必须写进阶段五的操作须知）**：`--ds-radius-lg` = **12px**，而旧 `--radius-lg` = **14px**。两个名字只差前缀、值不同。批量替换脚本与人工复核都必须按"值 → 令牌"查表，禁止按后缀替换。
> ⚠️ **2px / 3px 圆角**保持字面量（滚动条滑块、进度条末端等装饰细线），列为 C 类。

---

## 7. 试点建议

**首选：`web/src/components/NotificationBell.vue`**（A 17 / B 1，共 18 条）

选择理由：

1. **体量小且自包含**：单 `.vue`，无子组件、无图表、无 `:deep()` 覆盖，diff 可控；
2. **类型覆盖全**：包含圆角（8px→`--ds-radius-md`）、间距（`12px 16px`→`--space-12 --space-16`）、字号（13/14px）、字重（500/600）、语义色（`#f59e0b`→`--warning`、`#ef4444`→`--danger`）五类，能验证整条替换链路；
3. **刚修过 D1**：该组件原引用 7 个未定义变量导致"深色主题恒为浅色"，修复后深色主题表现会明显变化，**肉眼即可验证试点没有回退**；
4. **有现成测试**：`NotificationBell.test.ts`（8 例）能守住结构不回归。

**备选：`web/src/views/DownloadQueue.vue`**（9 条，全 A、零 TODO）—— 适合验证"纯机械替换不改视觉"。

**试点执行记录（2026-11-21，commit `cdee6c46`）**：`NotificationBell.vue` 的 A 类 **17 条已全部替换**，B 类 1 条（`height: 8px` 状态圆点）按约定只加 `TODO: [Design Debt]` 不替换；C 类未动。四件套全绿（test 421 passed 与试前一致）。

**全量替换记录（2026-11-21，5 批独立提交）**：

| 批次 | 范围 | A | B(TODO) | 提交通道 |
|---|---|---|---|---|
| 5-1 | `views/settings/`（8 文件） | 118 | 6 | `e0fdd780` |
| 5-2 | `components/dashboard/`（10 文件，TaskTrendCard 全 C） | 204 | 22 | `fd9b5c69` |
| 5-3 | `views/`（21 文件） | 272 | 37（+2 内联待人工） | `231cd5cc` |
| 5-4 | `components/` 非 dashboard（16 文件） | 333 | 38（+1 旧圆角别名 TODO） | `9d0ec26b` |
| 5-5 | `style.css`（1 文件） | 35 | 9 | `b48c7e77` |
| 合计 | — | **979** | **113 TODO + 2 内联待人工** | — |

- 每批独立提交、独立跑四件套（type-check / lint / test / build），测试恒为 **421 passed**；
- 5-3 首次应用时替换器把 `margin: 0 0 20px` 错包为 `var(0 0 var(--space-20))`，被 build 拦下，回退重做后入库，**错误未进任何提交**；
- 全量后复扫：**A=0 / B=150 / C=559 / D=0**（P5-4/P5-5 收紧）（A-51 减 3 条；P5-1 再减 6 条），全树无 `var(0…` / `var(var(…)`。

**试点发现的既有缺口**：状态圆点色 `--warning` 在浅色底上仅 2.15:1（green 主题 2.05:1），低于非文本对比度 3:1；该值替换前就是同色字面量 `#f59e0b`，**非本次引入**，登记为 DT-12。

**不建议做试点**：`views/settings/shared.css`（68 条，含 5 条 B 与跨 Tab 共享语义）、`components/NotificationConfig.vue`（66 条）、`style.css`（44 条，其中 93 处 PrimeVue 覆盖属 RETAINED 白名单，误改会破坏 a11y 修复）。

---

## 8. TODO 清单（`[Design Debt]` 与后续决策）

| 编号 | 事项 | 现状 | 建议时点 |
|---|---|---|---|
| DT-01 | **8pt 网格收敛**：off-grid 档 `1/2/3/6/7/9/14/18/30px` 已在令牌中按实测保留 | 19 档中 9 档 off-grid | 阶段五之后单独走视觉走查，不在本轮改值 |
| DT-02 | **字号语义化收敛**：`--font-size-9/10/42/72` 无语义别名（42/72 仅登录页 hero） | 16 档数字基座 | 与 DT-01 同批 |
| DT-03 | **`--color-on-primary` 缺失**：主色底白字仍是 `#fff` 字面量（B 类 12 处） | 未定义 | 需先在四主题里定义取值并过对比度测试，再替换 |
| DT-04 | **无令牌色**：B 类颜色集中在 `#fff`/`#ffffff`（12 处，缺 `--color-on-primary`）、半透明 overlay `rgba(...)`（约 20 处，缺 overlay 令牌）与 `#8b5cf6`（1 处）。注：`#e74c3c`(7) / `#6b7280`(3) / `#ccc`(3) 实测**均为 `var(--defined-token, 字面量)` 的死 fallback**，归 C 类，不是缺口 | B 类 | 需产品确认 overlay/on-primary 是否建令牌 |
| DT-05 | **阴影组合值无令牌**：12 处自定义 `box-shadow` | B 类 | 评估是否补 `--shadow-*` 档位 |
| DT-06 | **布局尺寸是否令牌化**：`height: 60px/100px/400px` 等 32 处 | B 类 | 默认不令牌化（任务包禁止把布局尺寸纳入），仅登记 |
| DT-07 | **圆角命名冲突**：`--ds-radius-lg(12)` vs `--radius-lg(14)` | 见 §6 | 阶段五前决定：旧名改档或新令牌改名 |
| DT-08 | **`--btn-height-md:34px` 的语义偏差**：实测 34px 消费者是仪表盘图标方块（已另设 `--icon-tile-md/sm`），`.p-button` 无固定高度 | 锁定值 | 按钮高度统一方案确定后再接线 |
| DT-09 | **RETAINED 白名单进基线**：93 处 PrimeVue 覆盖 + 日期选择器/表格表头属已批准例外 | C 类 | 阶段六写入 G-055 基线 |
| DT-10 | **PrimeVue 组件作用域 token 限制**：`--p-datatable-*` 等不在 `:root`，根注入无效 | 已在 `RETAINED_CSS_OVERRIDES` 记录 | 升级 PrimeVue 时重新评估 |
| DT-11 | **死 fallback 清理**：28 处 `var(--已定义令牌, 字面量)` 的 fallback 已无意义（如 `var(--border-light, #ccc)`） | C 类，不影响视觉 | 可随阶段五顺手清，需单独 commit |
| DT-12 | **`--warning` 状态圆点对浅色底不足 3:1**：light 2.15 / green 2.05（dark 8.76 / blue 9.95 通过）。试点 `NotificationBell.vue` 的 `.item-dot` 逐主题实测；替换前为同色字面量 `#f59e0b`，非试点引入 | 既有取值 | 需调 `--warning` 或新增 `--warning-indicator` 语义令牌；属独立决策，不在令牌替换批次内 |

---

## 9. 排除清单说明（C 类为什么不动）

| 排除理由 | 处置依据 |
|---|---|
| 令牌定义（`:root` / `--*` 声明） | 它们是真相源，不是"硬编码使用" |
| `var(--x, <字面量>)` fallback | D1 修复后 fallback 已基本删除；残留的随令牌变化，替换会破坏降级 |
| PrimeVue 组件覆盖（`style.css` 内 `html .p-*` 等） | 均为 a11y 修复产物，`style.css` 原位有 `RETAINED` 理由注释；属已批准例外 |
| SVG 图表（`TaskTrendCard.vue` 整体） | 配色与数据绑定（柱高/渐变/阈值色），令牌化会与数据语义耦合 |
| 布局尺寸：`width/min-width/max-width/百分比/fr/calc/clamp` | 任务包明确排除；它们不是视觉令牌 |
| 相对单位：`rem/em/vh/vw` | 与根字号/视口相关，不属固定档位 |
| 装饰细线：`height:1-3px`、`border-radius:2-3px`、`border-radius:50%` | 结构线/圆形，不是尺度语义 |
| 滤镜：`blur()/drop-shadow()` | 效果参数，无令牌语义 |
| 无字面量：`0/auto/inherit/none/transparent` | 不需要令牌 |

---

## 10. 回滚说明

| 目标 | 操作 | 影响 |
|---|---|---|
| 撤销全部（回到 `main`） | `git checkout main`（分支未合并时） | 无 |
| 撤销某一阶段 | `git revert <该阶段 commit>` | 阶段独立提交，互不依赖 |
| 只撤销缺陷修复 | `git revert <fix(theme) commit>` | 令牌文件与新尺度层保留；D1 死变量回归（会导致深色主题再次变浅，**不建议长期回滚**） |
| 只撤销令牌文件 | `git revert <chore: add design tokens>` | 需同时回退 `main.ts` 的 import（同一 commit 内）；不撤销任何既有样式 |
| 只撤销门禁 | `git revert <chore: add design token gate G-055>` + 从 `check_all.sh`/CI 摘除 | 机制恢复为人工评审 |

**回滚安全性依据**：阶段一（令牌文件、接线）不改任何既有值；阶段二（`fix(theme)`）是独立 commit；阶段三–五每步单独提交。`design-tokens.css` 除 `main.ts` 一处 `import` 外无消费者，回滚它不会引起视觉变化。

---

## 11. 验证方式

**全量替换后（2026-11-21，每批各跑一遍，结果一致）**：

```bash
cd web
pnpm.cmd run type-check   # exit 0
pnpm.cmd run lint         # exit 0（304 warnings / 0 errors，存量降级为 warn）
pnpm.cmd test             # 50 files / 421 tests passed
pnpm.cmd run build        # exit 0（dist CSS 含 --space-* / --ds-radius-* / --btn-height-*）
```

**审计可复现**：

```bash
python scripts/audit_design_tokens.py --check   # 输出 A/B/C/D 计数，不写文件
python scripts/audit_design_tokens.py           # 刷新本文件 §4（默认全量，不截断）
```

**全量后的门禁输入**：**B=150**（P5-4/P5-5 后；`100%` 50 次 + `vh/fr/fit-content` 10 次）+ **C=559**（A-51 消除 1 条 `width:20px`）；全树 TODO 文本 114 处（113 B + 1 旧圆角别名）。G-055 的棘轮基线按此生成，只含 C 类分组、B 类 TODO 项与 2 条内联白名单；A 类为 0 表示"任何新增可映射硬编码当场红灯"。三处口径（本节 / §0 / 基线文件 `scripts/design_token_baseline.json`）必须一致。

**修复的守护测试**：`web/src/styles/design-tokens.test.ts`（6 例）—— ① `var()` 无未定义引用；② `style.css` 默认层与 `themes.ts` light 一致；③ 无失效文档引用；④ 令牌文件无颜色字面量；⑤ 不覆盖旧 `--radius-*`；⑥ 关键尺度令牌齐备。反向验证已做：注入 `var(--definitely-undefined)` 与 `--ds-bad: #ff00ff` 均报错，恢复后 6 passed。

---

## 12. 交付四要素（2026-11-21 收口）

### 12.1 变更摘要

分支 `chore/design-tokens` → `main`（PR #9，draft）。**截至 7-2 提交：16 个提交 / 82 files / +6712 −801**；7-3 追加本附录后总数为 17 个提交（数字锚定到 7-2，避免『本附录自身也计入』的自指矛盾）。

| 类别 | 文件数 | 内容 |
|---|---|---|
| `web/src` | 61 | 令牌层 63 令牌 + 979 条 A 类替换 + D1–D5 修复 |
| `docs` | 13 | 审计报告、治理登记、08/26/27 回写、债务台账、CI 教训 |
| `scripts` | 4 | 审计工具、G-055 门禁、基线（611 条目）、`check_all.sh` 接线 |
| `tests` | 2 | 令牌守护 6 例 + CI 配置回归 3 例 + 门禁受控 9 例 |
| `.github` | 2 | `ci.yml` G-029 范围、`deep-gate.yml` 补 pytest |

阶段产物：① 主题无关尺度层（无颜色字面量）；② D1 未定义变量 11 名/26 处清零、D2 默认层漂移修正、D4/D5 文档与引用清理；③ 审计 1722 命中（A 979 / B 115 / C 628 / D 0；历史快照）；④ 全量替换 A 类 979 条（试点 + 5 批，每批独立提交与四件套）；⑤ G-055 棘轮门禁 + 基线；⑥ PR 路径两处既有 CI 缺陷修复。

### 12.2 验收证据

| 证据 | 结果 |
|---|---|
| 每批四件套 | type-check 0 / lint 0 errors（304 warnings 未增）/ vitest **421 passed** / build 0 |
| 本地门禁 | `check_all.sh --fast --guards --local` exit 0；`--ci`（CI 严格模式复刻）exit 0 |
| 审计可复现 | `audit_design_tokens.py --check` → A=0 / B=150 / C=559 / D=0；报告重跑幂等 |
| 门禁反证 | 真实仓库注入 hex / 固定像素 / 内联 height 均 exit 1；受控测试 9 例；空范围 G-029 非 0 退出 |
| **PR #9 CI（`bc061a9f`）** | CI/CD run [44894805257](https://github.com/leanmore/PilotStd/actions/runs/44894805257) **success**（10 jobs，3 skipped 属非 main）；Deep Gate run [44894805295](https://github.com/leanmore/PilotStd/actions/runs/44894805295) **success** |
| 关键步骤级 | `G-055`（test-frontend step 8）success ；`G-029`（repo-compliance step 7）success ；`Run GUI unit tests` success ；`deep-gate-check` success |

### 12.3 回滚说明

**文档类提交按逆序**（先撤本 §12 交付摘要 → 再撤 7-1 的 08/26/27 与债务台账回写 → 最后撤 7-2 能力矩阵时间戳）——§12 引用了 7-1 定义的 A-50/A-51/A-52、V-19，先撤 7-1 会让引用悬空；**代码类提交按粒度独立回滚**，互不依赖：

```bash
git revert 5f52a4d9   # 只撤 08/26/27 + 债务台账回写
git revert 34a2b1c1   # 只撤能力矩阵时间戳
git revert bc061a9f   # 只撤 PR 路径 CI 配置修复（会退回 G-029 在 PR 下误报）
git revert 00097f12   # 只撤 G-055（删基线后门禁 exit 2，不会静默通过）
git revert b48c7e77   # 只撤 style.css 批；其余 4 批同理
git revert 53b7d3ee   # 只撤 D1–D5（会让 var() 失去定义，不建议单独回滚）
```

- **令牌文件（`2bc21202`）与缺陷修复（`53b7d3ee`）是其余替换的前提**，单独回滚它们会让 979 处 `var()` 失去定义；
- 回滚任意替换批次后，对应文件恢复字面量，视觉等价（A 类映射均为同值）。

### 12.4.1 视觉影响登记（A-50，2026-11-21）

- **变更性质**：状态色变深，**非品牌色变更**（品牌色 `--primary*` 未动）。
- **影响面**：`NotificationBell` 的状态圆点（非文本，≥3:1）；`LogBar` 的 `log-warn` 行文字（正文，≥4.5:1）；
  `style.css` 的 `.mp-badge-warning`（`--warning` 文字 on `--warning-bg`）随之变深，可读性提升。
- **取值**：light/green `#f59e0b → #ad4f08`；`--warning-bg` 的色相跟随（alpha 不变：0.12）。
- **未动**：dark/blue 仍 `#fbbf24`（对各自 bg 8.31 / 8.69，达标）。

### 12.4 遗留清单

| 编号 | 内容 | 状态 |
|---|---|---|
| **DT-12 / A-50** | `--warning` 对浅色底不足：light 1.96/2.15、green 1.91/2.05（LogBar 文字在 `--bg` 上需 4.5，圆点需 3） | **已修**：light/green 改 `#ad4f08`（light-bg 4.92 / green-bg 4.79 / light-surface 5.39），dark/blue 复测 8.31/8.69 不动；同步 `themes.ts` 与 `style.css`；见 §12.4 视觉影响与 `27` #109 |
| **A-51** | 2 条内联高度（`PendingView:90` 20px、`SystemResources:49` 24px）在 G-055 白名单内 | 待模板重构；禁止为过门禁单独加 class |
| **A-52** | B 类 115 条无令牌硬编码（113 TODO + 2 内联），受棘轮按基线次数保护 | 按类补令牌后批量替换 |
| **V-19** | `no-literal` 177 条口径收紧风险（收紧会产生大量 `[STALE]`） | 观察；一次涌现 >20 行需先重生成基线并人工评审 |
| **D2 结构性遗留** | 令牌"双层真相"仍在：测试只锁 light 主题与默认层一致，**其余三主题默认值无校验** | 未修（结构性，需另行设计） |
| **G-013 误报** | 提交信息含 `fix` 且改动全为文档时，规则 0 仍要求带 tests/ 变更 | **已修**（2026-11-21，PR 见 `27` #112）：新增 `is_docs_only()` 纯文档豁免（路径集合判定，含代码不豁免、空改动不豁免）；10 例回归 + `gates.md`/`ci-lessons.md` 登记 |

