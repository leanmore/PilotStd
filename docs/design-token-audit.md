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
| 命中总数 | **1722** 条（不含已令牌化声明 859 条、与视觉无关的声明 1095 条） |
| A 精确映射 | **979** 条 —— 值直接命中已定义令牌，可机械替换 |
| B 近似映射 | **115** 条 —— 无精确令牌，替换前必须人工确认并在行上方加 `/* TODO: [Design Debt] ... */` |
| C 排除 | **628** 条 —— 令牌定义、`var()` fallback、PrimeVue 覆盖白名单、SVG 图表、布局尺寸等（理由见 §4.2） |
| D 缺陷 | **0** 条 —— 修复前为 11 个未定义变量 / 26 处引用（D1），已清零并由测试守护 |
| 涉及文件 | 60 / 66（`styles/design-tokens.css` 与 `theme.css` 无命中） |
| 试点组件 | **`components/NotificationBell.vue`**（18 条：A 17 / B 1） |

**核心判断**：本仓的颜色令牌层已经存在且质量不低（四主题 + a11y 契约测试），真正缺的是**与主题无关的尺度层**（间距/字号/字重/行高/圆角/尺寸）和**引用完整性门禁**。因此本报告的主战场是尺度类硬编码——A 类 979 条按属性分布为：`font-size` 309、`gap` 180、`margin` 175、`padding` 168、`font-weight` 110，五项合计 942（96%），颜色类仅占 33 条。

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

共 **1094** 条（A 979 / B 115）。

| 文件路径 | 行号 | 当前硬编码值 | 样式属性 | 建议令牌 | 匹配置信度 | 备注 |
|---|---|---|---|---|---|---|
| components/AppHeader.vue | 106 | 60px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppHeader.vue | 107 | 0 24px | padding | 0 var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 108 | rgba(255, 255, 255, 0.8) | background | （无） | 低 | 无对应语义令牌 |
| components/AppHeader.vue | 112 | 0 1px 3px rgba(0, 0, 0, 0.05), 0 4px 12px -4px rgba(0, 0, 0, 0.08) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppHeader.vue | 122 | rgba(30, 41, 59, 0.85) | background | （无） | 低 | 无对应语义令牌 |
| components/AppHeader.vue | 128 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 134 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 138 | 18px | font-size | --font-size-18 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 139 | 800 | font-weight | --font-weight-extrabold | 高 |  |
| components/AppHeader.vue | 148 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 149 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/AppHeader.vue | 151 | 16px | padding-left | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 158 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 159 | 8px 14px | padding | var(--space-8) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 165 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 166 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/AppHeader.vue | 191 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 206 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 207 | 6px 12px | padding | var(--space-6) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 208 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 209 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/AppHeader.vue | 215 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 219 | 0 16px | padding | 0 var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 225 | 56px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppHeader.vue | 226 | 0 12px | padding | 0 var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 228 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 229 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 229 | 12px | padding-left | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 230 | 6px 10px | padding | var(--space-6) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 231 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| components/AppHeader.vue | 236 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 241 | 40px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppHeader.vue | 242 | 0 16px | padding | 0 var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppHeader.vue | 245 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 189 | 72px | padding-bottom | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 207 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 208 | 32px 36px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 218 | 20px 16px | padding | var(--space-20) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 232 | 68px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 233 | 0 8px | padding | 0 var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 234 | env(safe-area-inset-bottom) | padding-bottom | （无） | 中 | 含混合单位/calc，需人工确认 |
| components/AppLayout.vue | 235 | rgba(255, 255, 255, 0.9) | background | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 238 | 1px solid rgba(226, 232, 240, 0.5) | border-top | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 239 | 0 -2px 16px rgba(0, 0, 0, 0.06) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppLayout.vue | 245 | rgba(15, 23, 42, 0.9) | background | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 246 | rgba(51, 65, 85, 0.5) | border-top-color | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 253 | 3px | gap | var(--space-3) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 254 | 8px 4px | padding | var(--space-8) var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 256 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 257 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/AppLayout.vue | 273 | 0 0 3px 3px | border-radius | （无） | 中 | 非令牌圆角档位 |
| components/AppLayout.vue | 277 | 18px | font-size | --font-size-18 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 287 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/AppLayout.vue | 298 | 24px 20px | padding | var(--space-24) var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 303 | 16px 12px | padding | var(--space-16) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 306 | 64px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 307 | 6px 2px | padding | var(--space-6) var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 308 | 17px | font-size | --font-size-17 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 309 | 9px | font-size | --font-size-9 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 316 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 321 | 10px 4px | padding | var(--space-10) var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 334 | 56px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppLayout.vue | 340 | #ffffff | color | （无） | 低 | 无对应语义令牌 |
| components/AppLayout.vue | 341 | 22px | font-size | --font-size-22 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 345 | 0 4px 12px rgba(0, 0, 0, 0.15) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppLayout.vue | 356 | 0 6px 16px rgba(0, 0, 0, 0.2) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppLayout.vue | 358 | 1 | line-height | --line-height-none | 高 |  |
| components/AppLayout.vue | 362 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/AppLayout.vue | 380 | 6px | padding | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 386 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 388 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppLayout.vue | 393 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 401 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/AppLayout.vue | 408 | 4px 6px | margin | var(--space-4) var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 77 | 2px 0 8px rgba(0, 0, 0, 0.03) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppSidebar.vue | 85 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 86 | 20px 20px 16px | padding | var(--space-20) var(--space-20) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 91 | 20px 0 | padding | var(--space-20) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 94 | 22px | font-size | --font-size-22 | 高 | 实测档位 1:1 |
| components/AppSidebar.vue | 99 | 17px | font-size | --font-size-17 | 高 | 实测档位 1:1 |
| components/AppSidebar.vue | 100 | 800 | font-weight | --font-weight-extrabold | 高 |  |
| components/AppSidebar.vue | 109 | 12px 12px | padding | var(--space-12) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 117 | 12px 8px | padding | var(--space-12) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 122 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 123 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 127 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/AppSidebar.vue | 128 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/AppSidebar.vue | 129 | 4px | margin-bottom | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 143 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/AppSidebar.vue | 144 | 0 2px 8px rgba(99, 102, 241, 0.08) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppSidebar.vue | 154 | 24px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/AppSidebar.vue | 156 | 0 4px 4px 0 | border-radius | （无） | 中 | 非令牌圆角档位 |
| components/AppSidebar.vue | 157 | 2px 0 8px rgba(99, 102, 241, 0.3) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| components/AppSidebar.vue | 162 | 17px | font-size | --font-size-17 | 高 | 实测档位 1:1 |
| components/AppSidebar.vue | 174 | 12px | padding | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 179 | 12px 8px | padding | var(--space-12) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 184 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 186 | 10px | padding | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 194 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/AppSidebar.vue | 195 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/AppSidebar.vue | 203 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| components/AppSidebar.vue | 208 | 12px 14px | padding | var(--space-12) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/AppSidebar.vue | 209 | 12px | padding | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 88 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 88 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 101 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 101 | 4px | margin-left | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 109 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/CacheManager.vue | 109 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 109 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 110 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 111 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 111 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 120 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 127 | 20px | gap | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 127 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 129 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 130 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 130 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/CacheManager.vue | 130 | 2px 0 4px | margin | var(--space-2) 0 var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 131 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 131 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 132 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 132 | 4px 0 | padding | var(--space-4) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 134 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/CacheManager.vue | 135 | 12px | padding-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 136 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/CacheManager.vue | 136 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/DynamicSettingField.vue | 214 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/DynamicSettingField.vue | 215 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/DynamicSettingField.vue | 223 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/DynamicSettingField.vue | 229 | 7px 10px | padding | var(--space-7) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/DynamicSettingField.vue | 234 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/FavoriteStatusTag.vue | 65 | 1.25 | line-height | --line-height-snug | 高 |  |
| components/FileMonitor.vue | 160 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/FileMonitor.vue | 162 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 171 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 187 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 191 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 208 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 216 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 216 | 12px 16px | padding | var(--space-12) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 216 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 217 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 218 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/FileMonitor.vue | 219 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/FileMonitor.vue | 219 | 1px 6px | padding | var(--space-1) var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 220 | 18px | padding | var(--space-18) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 221 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 222 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/FileMonitor.vue | 222 | 6px | margin-bottom | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 223 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/FileMonitor.vue | 223 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/LogBar.vue | 183 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/LogBar.vue | 186 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/LogBar.vue | 194 | 6px 12px | padding | var(--space-6) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/LogBar.vue | 199 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/LogBar.vue | 200 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/LogBar.vue | 202 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/LogBar.vue | 205 | 6px 12px | padding | var(--space-6) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/LogBar.vue | 209 | 1.5 | line-height | --line-height-normal | 高 |  |
| components/LogBar.vue | 214 | 12px | padding | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/LogBar.vue | 224 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/LogBar.vue | 231 | rgba(99, 102, 241, 0.3) | background | --primary-border | 中 | 按值精确匹配 |
| components/LogBar.vue | 241 | #555 | background | （无） | 低 | 无对应语义令牌 |
| components/LogBar.vue | 246 | 4px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/NotificationBell.vue | 163 | 8px | border-radius | --ds-radius-md | 高 |  |
| components/NotificationBell.vue | 173 | 12px 16px | padding | var(--space-12) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 177 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/NotificationBell.vue | 178 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/NotificationBell.vue | 195 | 10px 16px | padding | var(--space-10) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 205 | #f59e0b | background | --warning | 高 |  |
| components/NotificationBell.vue | 206 | #ef4444 | background | --danger | 高 |  |
| components/NotificationBell.vue | 217 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/NotificationBell.vue | 220 | 12px | margin-right | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 221 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 231 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/NotificationBell.vue | 232 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/NotificationBell.vue | 237 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/NotificationBell.vue | 239 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 249 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationBell.vue | 251 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 255 | 40px 20px | padding | var(--space-40) var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationBell.vue | 261 | 8px 16px | padding | var(--space-8) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 72 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 72 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 73 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 75 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 82 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 83 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 86 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 96 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 96 | 0 0 10px | margin | 0 0 var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 127 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 128 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 145 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 151 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 151 | 10px | margin-top | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 153 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 163 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 163 | 4px 0 0 | margin | var(--space-4) 0 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 170 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 198 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 200 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 201 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 204 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 212 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 212 | 8px | margin-left | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 216 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 219 | 16px | margin-left | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 228 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 238 | 14px 18px | padding | var(--space-14) var(--space-18) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 244 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 244 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/NotificationConfig.vue | 247 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 248 | 2px | padding | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 251 | 16px 18px | padding | var(--space-16) var(--space-18) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 257 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 258 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 258 | 4px | margin-bottom | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 259 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 260 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 261 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 261 | 8px | padding-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 261 | 8px 0 6px | margin | var(--space-8) 0 var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 263 | 8px | padding-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 263 | 10px 0 6px | margin | var(--space-10) 0 var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 264 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 264 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/NotificationConfig.vue | 265 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 265 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 265 | 1.5 | line-height | --line-height-normal | 高 |  |
| components/NotificationConfig.vue | 268 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 268 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 269 | 10px | margin-top | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 269 | 8px | padding-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 270 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 270 | 4px | margin-bottom | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 271 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 271 | 12px | margin-right | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 271 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 272 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 273 | 10px | margin-top | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 274 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/NotificationConfig.vue | 274 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/NotificationConfig.vue | 274 | 6px 0 2px | margin | var(--space-6) 0 var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 277 | 4px 8px | gap | var(--space-4) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 277 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 280 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/NotificationConfig.vue | 282 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 126 | 16px | padding | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 132 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 133 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 134 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 134 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/RouteDebugPanel.vue | 135 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 136 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 138 | 8px 12px | padding | var(--space-8) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 139 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 142 | 8px 16px | padding | var(--space-8) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 143 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 143 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/RouteDebugPanel.vue | 143 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/RouteDebugPanel.vue | 146 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 147 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 149 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 149 | 6px 8px | padding | var(--space-6) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 151 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 153 | 8px | padding | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 153 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 153 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 156 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 157 | 8px 12px | padding | var(--space-8) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 157 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 157 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/RouteDebugPanel.vue | 160 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 161 | 8px 12px | padding | var(--space-8) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 161 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/RouteDebugPanel.vue | 165 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/RouteDebugPanel.vue | 166 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/RouteDebugPanel.vue | 168 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 170 | 1px 6px | padding | var(--space-1) var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/RouteDebugPanel.vue | 170 | 10px | border-radius | --radius | 高 | 旧令牌 |
| components/RouteDebugPanel.vue | 170 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/SettingsTabAppearanceMixed.vue | 65 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/SettingsTabAppearanceMixed.vue | 78 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/SettingsTabAppearanceMixed.vue | 124 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TableLoadFooter.vue | 44 | 12px 16px | padding | var(--space-12) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TableLoadFooter.vue | 46 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/TableLoadFooter.vue | 54 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TableLoadFooter.vue | 57 | 4px 12px | padding | var(--space-4) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TableLoadFooter.vue | 61 | 4px | border-radius | --ds-radius-xs | 高 |  |
| components/TableLoadFooter.vue | 63 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/TableLoadFooter.vue | 68 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/TableLoadFooter.vue | 71 | #ca8a04 | color | （无） | 低 | 无对应语义令牌 |
| components/TableLoadFooter.vue | 74 | 20px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/TaskManager.vue | 145 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 155 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 160 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 175 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 179 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 182 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 186 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 196 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 204 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 204 | 8px | padding | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 204 | 4px | border-radius | --ds-radius-xs | 高 |  |
| components/TaskManager.vue | 206 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 206 | 4px 0 | margin | var(--space-4) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 216 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 220 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 236 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 240 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 241 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 250 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 251 | 6px 14px | padding | var(--space-6) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/TaskManager.vue | 251 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/TaskManager.vue | 253 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/UnifiedFilterBar.vue | 61 | 999px | border-radius | --ds-radius-pill | 高 |  |
| components/UnifiedFilterBar.vue | 62 | 4px | padding | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/UnifiedFilterBar.vue | 63 | 2px | gap | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/UnifiedFilterBar.vue | 69 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/UnifiedFilterBar.vue | 70 | 6px 14px | padding | var(--space-6) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/UnifiedFilterBar.vue | 71 | 999px | border-radius | --ds-radius-pill | 高 |  |
| components/UnifiedFilterBar.vue | 86 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/UnifiedFilterBar.vue | 90 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 381 | 24px | margin-top | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 440 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/ValidityConfig.vue | 440 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 440 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 440 | 8px | padding-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 441 | 16px 20px | gap | var(--space-16) var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 441 | 14px | margin-bottom | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 442 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 443 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 443 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/ValidityConfig.vue | 444 | 36px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/ValidityConfig.vue | 445 | 36px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/ValidityConfig.vue | 446 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 446 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 450 | 24px | gap | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 450 | 12px 16px | padding | var(--space-12) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 452 | 14px | margin-bottom | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 454 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 454 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 456 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/ValidityConfig.vue | 458 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 458 | 400 | font-weight | --font-weight-regular | 高 |  |
| components/ValidityConfig.vue | 460 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 460 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 461 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 461 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 462 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 463 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 463 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/ValidityConfig.vue | 464 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 465 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 465 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 466 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 467 | 7px 8px | padding | var(--space-7) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 468 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/ValidityConfig.vue | 468 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 469 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 469 | 16px 0 | padding | var(--space-16) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 470 | 2px | gap | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 470 | 10px | margin-top | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 471 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/ValidityConfig.vue | 471 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/ValidityConfig.vue | 476 | bold | font-weight | （无） | 低 | 非常规字重 |
| components/WechatTrustIP.vue | 157 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 157 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 158 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 160 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/WechatTrustIP.vue | 160 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/WechatTrustIP.vue | 164 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 179 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/WechatTrustIP.vue | 191 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/WechatTrustIP.vue | 212 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 220 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 272 | 20px | gap | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 272 | 12px 16px | padding | var(--space-12) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 272 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 273 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 274 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/WechatTrustIP.vue | 275 | 14px | gap | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 277 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 278 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/WechatTrustIP.vue | 278 | 4px | margin-bottom | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/WechatTrustIP.vue | 278 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 136 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 139 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 144 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 146 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 146 | rgba(99,102,241,0.12) | background | --primary-bg | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 147 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 149 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 149 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 150 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 153 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 155 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 155 | 10px 12px | padding | var(--space-10) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 160 | rgba(239,68,68,0.25) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 160 | rgba(239,68,68,0.04) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 161 | rgba(245,158,11,0.25) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 161 | rgba(245,158,11,0.04) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 164 | 36px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 166 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 166 | 800 | font-weight | --font-weight-extrabold | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 168 | rgba(99,102,241,0.1) | background | --primary-bg | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 169 | rgba(239,68,68,0.12) | background | --danger-bg | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 170 | rgba(245,158,11,0.12) | background | --warning-bg | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 173 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 173 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 174 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 177 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 177 | 9px | font-size | --font-size-9 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 177 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 178 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 184 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 185 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 185 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 186 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 186 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 187 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 187 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 189 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 191 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 191 | 20px 0 | padding | var(--space-20) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 192 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 122 | 20px | padding | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 135 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/AdapterStatusCard.vue | 137 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 138 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 139 | 12px | padding-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 147 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 150 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/dashboard/widgets/AdapterStatusCard.vue | 152 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 155 | 8px 10px | padding | var(--space-8) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 162 | 10px | padding | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 176 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 177 | 24px 0 | padding | var(--space-24) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 182 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 183 | 4px 0 | margin | var(--space-4) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 188 | 16px | padding | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusCard.vue | 189 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusCard.vue | 190 | 6px 8px | padding | var(--space-6) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 125 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 128 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 133 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 135 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 135 | rgba(59,130,246,0.12) | background | --info-bg | 高 |  |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 136 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 138 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 138 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 139 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 144 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 147 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 148 | 14px 10px 12px | padding | var(--space-14) var(--space-10) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 151 | rgba(59,130,246,0.3) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 151 | rgba(59,130,246,0.04) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 152 | rgba(239,68,68,0.2) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 152 | rgba(239,68,68,0.03) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 153 | rgba(245,158,11,0.2) | border-color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 153 | rgba(245,158,11,0.03) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 157 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 157 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 158 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 161 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 161 | 1.3 | line-height | --line-height-compact | 高 |  |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 172 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 173 | 9px | font-size | --font-size-9 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 175 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 182 | rgba(239,68,68,0.85) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 184 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 184 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 184 | #fff | color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 189 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 189 | 20px 0 | padding | var(--space-20) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 190 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 37 | 24px | font-size | --font-size-24 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 37 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 57 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 60 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 63 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 65 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/PendingItemsCard.vue | 65 | rgba(239,68,68,0.12) | background | --danger-bg | 高 |  |
| components/dashboard/widgets/PendingItemsCard.vue | 66 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 68 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 68 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/PendingItemsCard.vue | 69 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 71 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 73 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 73 | 10px 12px | padding | var(--space-10) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 79 | 2px 6px | padding | var(--space-2) var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 79 | 4px | border-radius | --ds-radius-xs | 高 |  |
| components/dashboard/widgets/PendingItemsCard.vue | 79 | 9px | font-size | --font-size-9 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 79 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/PendingItemsCard.vue | 80 | rgba(245,158,11,0.12) | background | --warning-bg | 高 |  |
| components/dashboard/widgets/PendingItemsCard.vue | 83 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 83 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/dashboard/widgets/PendingItemsCard.vue | 85 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 85 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 88 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 89 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 89 | 4px | padding-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PendingItemsCard.vue | 90 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PendingItemsCard.vue | 90 | 30px 0 | padding | var(--space-30) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PlaceholderWidget.vue | 23 | 20px | padding | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PlaceholderWidget.vue | 26 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/PlaceholderWidget.vue | 26 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/PlaceholderWidget.vue | 26 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/PlaceholderWidget.vue | 27 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/QuickActionsCard.vue | 134 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/QuickActionsCard.vue | 137 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/QuickActionsCard.vue | 140 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/QuickActionsCard.vue | 142 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/QuickActionsCard.vue | 142 | rgba(139,92,246,0.12) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/QuickActionsCard.vue | 143 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/QuickActionsCard.vue | 143 | #8b5cf6 | color | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/QuickActionsCard.vue | 145 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/QuickActionsCard.vue | 145 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/QuickActionsCard.vue | 147 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/QuickActionsCard.vue | 149 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/QuickActionsCard.vue | 156 | 22px | font-size | --font-size-22 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/QuickActionsCard.vue | 157 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/QuickActionsCard.vue | 157 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/dashboard/widgets/QuickActionsCard.vue | 158 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/QuickActionsCard.vue | 158 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 122 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 125 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 128 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 130 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 130 | rgba(245,158,11,0.12) | background | --warning-bg | 高 |  |
| components/dashboard/widgets/RecentAnnounceCard.vue | 131 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 133 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 133 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/RecentAnnounceCard.vue | 134 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 147 | 6px | margin-left | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 155 | 4px | padding-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 159 | 6px 0 | padding | var(--space-6) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 170 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 171 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/dashboard/widgets/RecentAnnounceCard.vue | 179 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 181 | 1px | margin-top | var(--space-1) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 185 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 186 | 30px 0 | padding | var(--space-30) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 191 | 12px 0 | padding | var(--space-12) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/RecentAnnounceCard.vue | 194 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/StatsCard.vue | 74 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 75 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 82 | linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08)) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/StatsCard.vue | 83 | 1px solid rgba(99,102,241,0.25) | border | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/StatsCard.vue | 93 | 100px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/StatsCard.vue | 94 | rgba(99,102,241,0.2) | background | --primary-border | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 100 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 102 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/StatsCard.vue | 102 | 500 | font-weight | --font-weight-medium | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 103 | 42px | font-size | --font-size-42 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/StatsCard.vue | 103 | 800 | font-weight | --font-weight-extrabold | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 103 | 1 | line-height | --line-height-none | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 104 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 110 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 113 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 114 | 8px 12px | padding | var(--space-8) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/StatsCard.vue | 120 | 32px | height | --icon-tile-sm | 中 | 图标方块尺寸 |
| components/dashboard/widgets/StatsCard.vue | 121 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/StatsCard.vue | 123 | rgba(245,158,11,0.12) | background | --warning-bg | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 124 | rgba(59,130,246,0.12) | background | --info-bg | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 125 | rgba(239,68,68,0.12) | background | --danger-bg | 高 |  |
| components/dashboard/widgets/StatsCard.vue | 126 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/StatsCard.vue | 127 | 18px | font-size | --font-size-18 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/StatsCard.vue | 127 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/SystemInfoCard.vue | 73 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 76 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 78 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 80 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/SystemInfoCard.vue | 80 | rgba(34,197,94,0.12) | background | --success-bg | 高 |  |
| components/dashboard/widgets/SystemInfoCard.vue | 81 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemInfoCard.vue | 83 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemInfoCard.vue | 83 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/SystemInfoCard.vue | 85 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 86 | 10px 0 | padding | var(--space-10) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 87 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemInfoCard.vue | 87 | 4px | margin-bottom | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 88 | 28px | font-size | --font-size-28 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemInfoCard.vue | 88 | 800 | font-weight | --font-weight-extrabold | 高 |  |
| components/dashboard/widgets/SystemInfoCard.vue | 90 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 91 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemInfoCard.vue | 92 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemInfoCard.vue | 93 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| components/dashboard/widgets/SystemInfoCard.vue | 97 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemInfoCard.vue | 97 | 600 | font-weight | --font-weight-semibold | 高 |  |
| components/dashboard/widgets/SystemInfoCard.vue | 101 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 90 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 93 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 96 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 98 | 34px | height | --icon-tile-md | 中 | 图标方块尺寸 |
| components/dashboard/widgets/SystemLogCard.vue | 98 | rgba(34,197,94,0.12) | background | --success-bg | 高 |  |
| components/dashboard/widgets/SystemLogCard.vue | 99 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 101 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 101 | 700 | font-weight | --font-weight-bold | 高 |  |
| components/dashboard/widgets/SystemLogCard.vue | 102 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 103 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 105 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 106 | 2px 8px | padding | var(--space-2) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 113 | rgba(0,0,0,0.08) | background | （无） | 低 | 无对应语义令牌 |
| components/dashboard/widgets/SystemLogCard.vue | 114 | 8px 10px | padding | var(--space-8) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 114 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 114 | 1.7 | line-height | --line-height-relaxed | 高 |  |
| components/dashboard/widgets/SystemLogCard.vue | 116 | 20px 0 | padding | var(--space-20) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 117 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 118 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 118 | 3px | margin-top | var(--space-3) | 高 | 8pt 网格外的档位已按实测保留 |
| components/dashboard/widgets/SystemLogCard.vue | 119 | 10px | font-size | --font-size-10 | 高 | 实测档位 1:1 |
| components/dashboard/widgets/SystemLogCard.vue | 125 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| style.css | 125 | rgba(99, 102, 241, 0.2) | border-color | （无） | 低 | 无对应语义令牌 |
| style.css | 127 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 128 | 2px 10px | padding | var(--space-2) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 128 | 999px | border-radius | --ds-radius-pill | 高 |  |
| style.css | 128 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| style.css | 128 | 600 | font-weight | --font-weight-semibold | 高 |  |
| style.css | 130 | rgba(34,197,94,0.12) | background | --success-bg | 高 |  |
| style.css | 131 | rgba(239,68,68,0.12) | background | --danger-bg | 高 |  |
| style.css | 132 | rgba(245,158,11,0.12) | background | --warning-bg | 高 |  |
| style.css | 134 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 138 | rgba(99, 102, 241, 0.04) | background | （无） | 低 | 无对应语义令牌 |
| style.css | 140 | 0 0 4px rgba(34,197,94,0.4) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| style.css | 141 | 0 0 14px rgba(34,197,94,0.7) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| style.css | 143 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| style.css | 144 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| style.css | 145 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| style.css | 161 | 600 | font-weight | --font-weight-semibold | 高 |  |
| style.css | 168 | 22px | font-size | --font-size-22 | 高 | 实测档位 1:1 |
| style.css | 172 | 17px | font-size | --font-size-17 | 高 | 实测档位 1:1 |
| style.css | 176 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| style.css | 180 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| style.css | 640 | 20px | padding | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 650 | 600 | font-weight | --font-weight-semibold | 高 |  |
| style.css | 652 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| style.css | 653 | 14px | margin-bottom | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 654 | 12px | padding-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 665 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 669 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 673 | 24px | margin-top | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 677 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 681 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 685 | 16px | margin-left | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 698 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| style.css | 703 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| style.css | 704 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 713 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 717 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 726 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| style.css | 727 | 4px 8px | padding | var(--space-4) var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 729 | 500 | font-weight | --font-weight-medium | 高 |  |
| style.css | 749 | 0 2px 2px 0 | border-radius | （无） | 中 | 非令牌圆角档位 |
| style.css | 772 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| style.css | 776 | 18px | font-size | --font-size-18 | 高 | 实测档位 1:1 |
| style.css | 789 | 6px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/AnnounceDetail.vue | 254 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 267 | 22px | font-size | --font-size-22 | 高 | 实测档位 1:1 |
| views/AnnounceDetail.vue | 268 | bold | font-weight | （无） | 低 | 非常规字重 |
| views/AnnounceDetail.vue | 270 | 1.8 | line-height | --line-height-loose | 高 |  |
| views/AnnounceDetail.vue | 271 | 0.5rem 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 276 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 284 | 1.8 | line-height | --line-height-loose | 高 |  |
| views/AnnounceDetail.vue | 290 | 0.5em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 296 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/AnnounceDetail.vue | 303 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| views/AnnounceDetail.vue | 307 | 1.8 | line-height | --line-height-loose | 高 |  |
| views/AnnounceDetail.vue | 308 | 0.25em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 313 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| views/AnnounceDetail.vue | 317 | 1.8 | line-height | --line-height-loose | 高 |  |
| views/AnnounceDetail.vue | 318 | 0.25em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 323 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| views/AnnounceDetail.vue | 327 | 1.8 | line-height | --line-height-loose | 高 |  |
| views/AnnounceDetail.vue | 328 | 0.25em 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 339 | 0.25rem 0.5rem | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/AnnounceDetail.vue | 345 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 183 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 183 | 6px 0 | padding | var(--space-6) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 187 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 188 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 197 | 40px 0 | padding | var(--space-40) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 204 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 205 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 205 | 4px 0 | margin | var(--space-4) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 207 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 209 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 210 | 14px 16px | padding | var(--space-14) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 211 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 212 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 212 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/AnnounceView.vue | 213 | 8px 0 0 | margin | var(--space-8) 0 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 214 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 214 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 214 | 4px 0 | padding | var(--space-4) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 219 | 28px | font-size | --font-size-28 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 219 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/AnnounceView.vue | 220 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 220 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 221 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/AnnounceView.vue | 221 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/AnnounceView.vue | 221 | 1.5 | line-height | --line-height-normal | 高 |  |
| views/BackupView.vue | 91 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/BackupView.vue | 91 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/BackupView.vue | 91 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/BackupView.vue | 93 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/BackupView.vue | 95 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/DownloadImport.vue | 209 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/DownloadQueue.vue | 66 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/DownloadQueue.vue | 66 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/DownloadQueue.vue | 66 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/DownloadQueue.vue | 67 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/DownloadQueue.vue | 68 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/DownloadQueue.vue | 69 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/DownloadQueue.vue | 70 | 8px 12px | padding | var(--space-8) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/DownloadQueue.vue | 71 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/DownloadQueue.vue | 72 | 32px 0 | padding | var(--space-32) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/FavoritesView.vue | 181 | 0 auto | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/ForbiddenView.vue | 27 | 12vh auto 0 | margin | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/ForbiddenView.vue | 29 | 32px | padding | var(--space-32) | 高 | 8pt 网格外的档位已按实测保留 |
| views/ForbiddenView.vue | 32 | 72px | font-size | --font-size-72 | 高 | 实测档位 1:1 |
| views/ForbiddenView.vue | 33 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/ForbiddenView.vue | 35 | 1 | line-height | --line-height-none | 高 |  |
| views/ForbiddenView.vue | 38 | 16px 0 8px | margin | var(--space-16) 0 var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/ForbiddenView.vue | 42 | 24px | margin-bottom | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| views/HomeView.vue | 75 | 16px | padding | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/HomeView.vue | 81 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/HomeView.vue | 81 | 22px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/HomeView.vue | 81 | rgba(239,68,68,0.85) | background | （无） | 低 | 无对应语义令牌 |
| views/HomeView.vue | 81 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/LoginView.vue | 59 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/LoginView.vue | 60 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/LoginView.vue | 68 | linear-gradient(135deg, #667eea 0%, #764ba2 100%) | background | （无） | 低 | 无对应语义令牌 |
| views/LoginView.vue | 69 | 44px 36px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/LoginView.vue | 70 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/LoginView.vue | 70 | 4px | margin-bottom | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/LoginView.vue | 71 | 22px | font-size | --font-size-22 | 高 | 实测档位 1:1 |
| views/LoginView.vue | 72 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/LoginView.vue | 72 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/LoginView.vue | 73 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/LoginView.vue | 73 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/LoginView.vue | 73 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/LoginView.vue | 75 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/LoginView.vue | 75 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 88 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 155 | 6px 0 0 | margin | var(--space-6) 0 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 156 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 157 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 157 | 0 0 6px | margin | 0 0 var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 179 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 180 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 180 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 182 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 199 | 0 0 12px | margin | 0 0 var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 200 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 207 | 8px | padding | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 211 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 211 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 223 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 223 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 223 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/NotificationLogsView.vue | 224 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 227 | 14px | gap | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 228 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 229 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 229 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/NotificationLogsView.vue | 230 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 230 | 1px | padding-bottom | var(--space-1) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 235 | 400px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/NotificationLogsView.vue | 247 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 249 | 10px 12px | padding | var(--space-10) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 250 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/NotificationLogsView.vue | 250 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 252 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 252 | 32px 0 | padding | var(--space-32) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 260 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/NotificationLogsView.vue | 267 | rgba(99, 102, 241, 0.2) | background | --primary-border | 高 |  |
| views/NotificationLogsView.vue | 282 | 4px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/NotificationLogsView.vue | 286 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 286 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 289 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 290 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 292 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/NotificationLogsView.vue | 294 | 4px 0 0 | margin | var(--space-4) 0 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 294 | 10px | padding | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/NotificationLogsView.vue | 294 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 171 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 171 | 6px 0 | padding | var(--space-6) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 182 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/OrganizeView.vue | 183 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 184 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 197 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 198 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 198 | 9px 13px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/OrganizeView.vue | 200 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 200 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 201 | 2px 6px | padding | var(--space-2) var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 201 | 4px | border-radius | --ds-radius-xs | 高 |  |
| views/OrganizeView.vue | 203 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/OrganizeView.vue | 205 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 208 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 208 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 209 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 209 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 210 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 211 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 212 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 212 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/OrganizeView.vue | 213 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/OrganizeView.vue | 214 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 214 | 6px 12px | padding | var(--space-6) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/OrganizeView.vue | 215 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/PendingView.vue | 79 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 90 | 20px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/PendingView.vue | 119 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 119 | 6px 0 | padding | var(--space-6) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 122 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/PendingView.vue | 124 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 138 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 139 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/PendingView.vue | 140 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/PendingView.vue | 140 | 6px | margin-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 143 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 144 | 14px | padding | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 147 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 147 | 6px | margin-bottom | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/PendingView.vue | 148 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/PendingView.vue | 148 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/PendingView.vue | 149 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/PendingView.vue | 150 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QualityView.vue | 75 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QualityView.vue | 75 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/QualityView.vue | 75 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/QualityView.vue | 77 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QualityView.vue | 79 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/QualityView.vue | 81 | 24px | padding | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QualityView.vue | 82 | 12px 0 8px | margin | var(--space-12) 0 var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QualityView.vue | 82 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| views/QueryHistory.vue | 65 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QueryHistory.vue | 65 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/QueryHistory.vue | 65 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/QueryHistory.vue | 66 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QueryHistory.vue | 67 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/QueryHistory.vue | 68 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/QueryHistory.vue | 69 | 8px 12px | padding | var(--space-8) var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/QueryHistory.vue | 70 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/QueryHistory.vue | 71 | 32px 0 | padding | var(--space-32) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 51 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 52 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 54 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 65 | linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%) | background | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 68 | 16px | border-radius | --ds-radius-xl | 高 |  |
| views/RegisterView.vue | 68 | rgba(255,255,255,0.06) | background | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 69 | 40px | padding | var(--space-40) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 69 | 1px solid rgba(255,255,255,0.1) | border | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 71 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 71 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 72 | 28px | font-size | --font-size-28 | 高 | 实测档位 1:1 |
| views/RegisterView.vue | 73 | 24px | font-size | --font-size-24 | 高 | 实测档位 1:1 |
| views/RegisterView.vue | 73 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/RegisterView.vue | 73 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 74 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/RegisterView.vue | 74 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 74 | rgba(255,255,255,0.5) | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 76 | 12px | padding | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/RegisterView.vue | 76 | 8px | border-radius | --ds-radius-md | 高 |  |
| views/RegisterView.vue | 76 | 1px solid rgba(255,255,255,0.1) | border | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 77 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/RegisterView.vue | 77 | rgba(255,255,255,0.05) | background | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 77 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 80 | rgba(255,255,255,0.3) | color | （无） | 低 | 无对应语义令牌 |
| views/RegisterView.vue | 82 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/RegisterView.vue | 82 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SchedulerStatus.vue | 82 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SchedulerStatus.vue | 82 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/SchedulerStatus.vue | 82 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/SchedulerStatus.vue | 85 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SchedulerStatus.vue | 85 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SchedulerStatus.vue | 87 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/SettingsView.vue | 379 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 382 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/SettingsView.vue | 408 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 408 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 409 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 410 | 6px 10px | padding | var(--space-6) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 421 | 4px | padding | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 424 | 10px 18px | padding | var(--space-10) var(--space-18) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 429 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/SettingsView.vue | 430 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/SettingsView.vue | 442 | #ffffff | color | （无） | 低 | 无对应语义令牌 |
| views/SettingsView.vue | 443 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/SettingsView.vue | 444 | 0 2px 8px rgba(99, 102, 241, 0.25) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| views/SettingsView.vue | 452 | 20px 24px | padding | var(--space-20) var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 456 | 24px | margin-top | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 461 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 466 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 467 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/SettingsView.vue | 467 | 8px | margin-left | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SettingsView.vue | 468 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 257 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 257 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 257 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/StandardsStatusView.vue | 258 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 258 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 263 | 28px | font-size | --font-size-28 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 263 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/StandardsStatusView.vue | 264 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 264 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 265 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 266 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 267 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 268 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 268 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/StandardsStatusView.vue | 269 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 269 | 1px | padding-bottom | var(--space-1) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 270 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 270 | 10px | margin-bottom | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/StandardsStatusView.vue | 271 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/StandardsStatusView.vue | 271 | 20px 0 | padding | var(--space-20) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/SystemResources.vue | 49 | 24px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/SystemResources.vue | 59 | 0 0 20px | margin | 0 0 var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SystemResources.vue | 59 | 20px | font-size | --font-size-20 | 高 | 实测档位 1:1 |
| views/SystemResources.vue | 59 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/SystemResources.vue | 60 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SystemResources.vue | 61 | 0 0 12px | margin | 0 0 var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SystemResources.vue | 61 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| views/SystemResources.vue | 62 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/SystemResources.vue | 62 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 480 | 20px | margin-bottom | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 481 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 482 | 9px 13px | padding | （无） | 中 | 含混合单位/calc，需人工确认 |
| views/TaskView.vue | 483 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 485 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 486 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 487 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 488 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 498 | 14px | gap | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 499 | 14px 18px | padding | var(--space-14) var(--space-18) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 506 | rgba(239,68,68,0.06) | background | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 509 | 32px | height | --icon-tile-sm | 中 | 图标方块尺寸 |
| views/TaskView.vue | 514 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 514 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/TaskView.vue | 517 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 518 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 519 | #fff | color | （无） | 低 | 无对应语义令牌 |
| views/TaskView.vue | 522 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 522 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/TaskView.vue | 523 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 523 | 2px | margin-top | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 525 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 527 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 528 | 4px | gap | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 528 | 10px | padding | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView.vue | 529 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 530 | 18px | font-size | --font-size-18 | 高 | 实测档位 1:1 |
| views/TaskView.vue | 530 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/TaskView.vue | 534 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 51 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 51 | 6px 0 | padding | var(--space-6) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 53 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 54 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/TaskView/TaskHistoryList.vue | 55 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/TaskView/TaskHistoryList.vue | 57 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 57 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/TaskView/TaskHistoryList.vue | 57 | 4px | margin-top | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 63 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 78 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/TaskView/TaskHistoryList.vue | 79 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabCircuit.vue | 81 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabCircuit.vue | 85 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabCircuit.vue | 89 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabNotification.vue | 26 | 24px 0 | margin | var(--space-24) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabNotification.vue | 27 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSchedule.vue | 191 | 20px | gap | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSchedule.vue | 192 | 10px 0 | padding | var(--space-10) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSchedule.vue | 201 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSchedule.vue | 206 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabSchedule.vue | 207 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/SettingsTabSchedule.vue | 213 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSchedule.vue | 216 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabSchedule.vue | 222 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabSchedule.vue | 226 | 12px | margin-top | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 316 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 323 | 8px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/SettingsTabSites.vue | 332 | 2px | margin-left | var(--space-2) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 337 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 338 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 339 | 8px | padding-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 345 | 3px | gap | var(--space-3) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 348 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabSites.vue | 349 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/SettingsTabSites.vue | 353 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabSites.vue | 354 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/settings/SettingsTabSites.vue | 356 | 4px 0 | padding | var(--space-4) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 363 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 364 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 365 | 6px | padding-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabSites.vue | 367 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabToken.vue | 115 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabToken.vue | 123 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabToken.vue | 126 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabToken.vue | 136 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabToken.vue | 137 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabToken.vue | 142 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabToken.vue | 142 | 1.6 | line-height | --line-height-body | 高 |  |
| views/settings/SettingsTabToken.vue | 143 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabToken.vue | 144 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabToken.vue | 144 | 16px | margin-top | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 100 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 109 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 109 | 6px 0 | padding | var(--space-6) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 110 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/SettingsTabUsers.vue | 111 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabUsers.vue | 112 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabUsers.vue | 123 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 131 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 140 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/SettingsTabUsers.vue | 140 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 141 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 146 | 8px | gap | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabUsers.vue | 158 | 8px | padding | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabValidity.vue | 99 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabValidity.vue | 103 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/SettingsTabValidity.vue | 107 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 19 | 24px | padding | var(--space-24) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 27 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/settings/shared.css | 29 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 30 | 18px | margin-bottom | var(--space-18) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 34 | 14px | padding-bottom | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 42 | 14px 20px | gap | var(--space-14) var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 44 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 47 | 8px 0 | gap | var(--space-8) 0 | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 48 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 67 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/shared.css | 68 | 9px | padding-top | var(--space-9) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 73 | 10px 14px | padding | var(--space-10) var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 78 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 93 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 94 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 94 | 8px | margin-left | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 97 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 101 | 16px | margin-bottom | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 102 | 8px | margin-top | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 108 | 12px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 109 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/settings/shared.css | 109 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 124 | 6px | gap | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 125 | 10px 16px | padding | var(--space-10) var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 131 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 132 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/shared.css | 143 | 20px | gap | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 148 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 150 | 8px | padding | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 156 | 13px | font-size | --font-size-13 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 159 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/shared.css | 161 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/settings/shared.css | 162 | 4px | padding | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 165 | 44px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 182 | 12px | height | （无） | 中 | 布局/控件尺寸，需确认是否令牌化 |
| views/settings/shared.css | 187 | 0 2px 4px rgba(0, 0, 0, 0.2) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| views/settings/shared.css | 195 | 16px | gap | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 200 | 20px | padding | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 222 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 222 | 8px | margin-bottom | var(--space-8) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 224 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 225 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/settings/shared.css | 228 | 4px 10px | padding | var(--space-4) var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 229 | 12px | border-radius | --ds-radius-lg | 高 |  |
| views/settings/shared.css | 231 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 231 | 600 | font-weight | --font-weight-semibold | 高 |  |
| views/settings/shared.css | 232 | 12px | font-size | --font-size-12 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 232 | 12px | margin-bottom | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 233 | 20px | gap | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 234 | 3px | gap | var(--space-3) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 235 | 11px | font-size | --font-size-11 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 235 | 500 | font-weight | --font-weight-medium | 高 |  |
| views/settings/shared.css | 236 | 16px | font-size | --font-size-16 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 236 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/settings/shared.css | 239 | 6px | padding-top | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 239 | 6px | padding-bottom | var(--space-6) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 242 | 14px | gap | var(--space-14) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 245 | 16px | padding | var(--space-16) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 250 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 254 | inset 0 2px 4px rgba(0, 0, 0, 0.05) | box-shadow | （无） | 低 | 阴影组合值，无令牌 |
| views/settings/shared.css | 256 | 10px | gap | var(--space-10) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 259 | 12px | gap | var(--space-12) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 277 | 16px 20px | padding | var(--space-16) var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 290 | 15px | font-size | --font-size-15 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 291 | 700 | font-weight | --font-weight-bold | 高 |  |
| views/settings/shared.css | 297 | 14px | font-size | --font-size-14 | 高 | 实测档位 1:1 |
| views/settings/shared.css | 300 | 4px | padding | var(--space-4) | 高 | 8pt 网格外的档位已按实测保留 |
| views/settings/shared.css | 309 | 20px | padding | var(--space-20) | 高 | 8pt 网格外的档位已按实测保留 |

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
| 涉及文件（有命中） | 60 |
| 命中总数 | 1722 |
| 已令牌化声明（不计入明细） | 859 |
| 与视觉令牌无关（布局属性等） | 1095 |
| A 精确映射 | 979 |
| B 近似映射（需 TODO） | 115 |
| C 排除 | 628 |
| D 缺陷 | 0 |

### 4.5 按属性分类

| 属性 | A | B | 合计 |
|---|---|---|---|
| font-size | 309 | 0 | 309 |
| gap | 180 | 0 | 180 |
| margin | 164 | 11 | 175 |
| padding | 161 | 7 | 168 |
| font-weight | 108 | 2 | 110 |
| background | 21 | 21 | 42 |
| height | 9 | 32 | 41 |
| color | 0 | 16 | 16 |
| border-radius | 12 | 3 | 15 |
| line-height | 15 | 0 | 15 |
| box-shadow | 0 | 12 | 12 |
| border | 0 | 11 | 11 |

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
| views/settings/shared.css | 68 |
| components/NotificationConfig.vue | 66 |
| style.css | 44 |
| components/ValidityConfig.vue | 43 |
| views/NotificationLogsView.vue | 42 |
| components/AppLayout.vue | 40 |
| components/dashboard/widgets/AdapterStatusAnnounceCard.vue | 40 |
| components/AppHeader.vue | 34 |
| components/RouteDebugPanel.vue | 34 |
| components/dashboard/widgets/AdapterStatusQueryCard.vue | 33 |

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

**本报告生成时（阶段二）**：

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
python scripts/audit_design_tokens.py           # 刷新本文件 §4
```

**修复的守护测试**：`web/src/styles/design-tokens.test.ts`（6 例）—— ① `var()` 无未定义引用；② `style.css` 默认层与 `themes.ts` light 一致；③ 无失效文档引用；④ 令牌文件无颜色字面量；⑤ 不覆盖旧 `--radius-*`；⑥ 关键尺度令牌齐备。反向验证已做：注入 `var(--definitely-undefined)` 与 `--ds-bad: #ff00ff` 均报错，恢复后 6 passed。
