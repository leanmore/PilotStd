# Aura Token 运行时同步可行性报告（Tech-Debt #8 · P0 调研）

> 调研方式：源码追踪（@primeuix/themes、@primeuix/styled、Aura preset）+ 验证环境浏览器运行时实证（Playwright）。
> 状态：P0 完成，零代码修改，`git status` 零差异。

## 一、版本策略确认

| 包 | 声明版本 | 策略 | 结论 |
|---|---|---|---|
| `primevue` | `^4.5.5` | 范围版本 + pnpm-lock.yaml 锁定 | 允许 4.x 内小版本升级，禁止大版本（5.x） |
| `@primeuix/themes` | `^1.2.5` | 同上 | 允许 1.x 内升级 |

**方案 C（升级 PrimeVue）暂不优先**：4.5.5 已是当前线较新版本，且官方 [issue #6388](https://github.com/primefaces/primevue/issues/6388) 表明 `darkModeSelector` 存在"初始化后不可改"的限制，升级不保证解决本问题，成本/风险高。

## 二、Token 解析链路（Aura preset 源码实证）

### 2.1 核心语义链（`base/index.mjs`）

```
content.color  → {text.color}        （语义引用）
text.color     → {surface.700}       （语义引用，light 模式）
surface.700    → slate.700 = #334155 （直接值）
```

### 2.2 组件 token 绑定（均指向 content 系）

| 组件 token | 引用 | 影响元素 |
|---|---|---|
| `--p-datepicker-header/weekday/date/selectMonth/selectYear` color | `{content.color}` | 日历面板全部文字 |
| `--p-datatable-header-cell-color`、`--p-datatable-body-cell-color`、`--p-datatable-row-color` | `{content.color}` | DataTable 表头/数据列 |
| `--p-card-color`、`--p-dialog-color` 等 | `{content.color}` | Card/Dialog 文字 |
| `--p-tag-*-color` | `{primary.color}` / `{text.muted.color}` | Tag 各 severity |

**关键结论**：绝大多数组件文字 token 是**语义引用**（`{content.color}`），直接值只有 surface 系色板。

## 三、运行时 API 能力边界（验证环境实证，Playwright）

| 测试 | 操作 | `--p-content-color` 结果 |
|---|---|---|
| T1 | `useTheme({ dark: true })`（动态 import 调用） | 不变（#334155） |
| T2 | `updatePreset(Aura)` | 不变（#334155） |
| T3 | **dark 初始化**（localStorage 预设 theme=dark → `options.dark=true`，`data-p-theme="dark"` 已设） | **仍 #334155**；仅 `--p-surface-0` 等 surface token 切换 |
| T4 | **方案 B**：`setProperty('--p-content-color', '#e2e8f0')` | **组件自动跟随**（日历 header/weekday/day 全部变浅，零 CSS 覆盖） |
| T5 | data-p-theme="dark" CSS 规则统计 | **darkRules 恒为 0**（Aura 不生成 data-p-theme 选择器规则） |

**能力边界结论**：
1. **方案 A（官方 API 运行时更新 content/text token）不可行**——`useTheme`/`updatePreset` 实测无效；dark 初始化也不改变 content token（PrimeVue 4.5.5 + Aura 1.2.5 当前行为：dark 模式仅切换 surface 系，text/content 系固定 light 值）。
2. **方案 B（CSS 变量覆盖 `--p-*` token）可行**——`setProperty` 修改 `--p-content-color` 后，所有绑定该 token 的组件（日历/表格/卡片等）自动跟随反白。这与现有 `updateSurfacePalette`（改 `--p-surface-*`）同路径，是唯一可靠的运行时同步机制。
3. **方案 C（升级）**：版本策略允许小版本升级，但 issue #6388 表明机制限制存在，不保证解决。

## 四、方案决策

### ✅ 推荐：方案 B —— 扩展 useThemeSync 的 token 注入

在 `useThemeSync` 中，除现有 `updateSurfacePalette`（surface 系）外，**按主题映射批量 `setProperty` 注入 text/content 系 token**：

```ts
// 目标（P1 映射表落地后）：
// blue/dark  → --p-content-color: #e2e8f0、--p-text-color: #e2e8f0、--p-text-muted-color: #94a3b8 ...
// light/green→ --p-content-color: #334155、--p-text-color: #334155 ...
```

优势：
- 与 updateSurfacePalette 同路径，已验证可靠（T4）
- 组件自动跟随（token 驱动），可移除 B+/B++ 全部 CSS 强制覆盖
- 不动组件逻辑，不升级依赖

### 备选：方案 C（升级 PrimeVue）
仅当 P2 实施中确认 4.5.5 存在无法绕过的限制时再评估（当前 T4 证明可绕过）。

## 五、P1 输入（token 映射表范围）

| 项目变量/主题 | 需注入的 Aura token |
|---|---|
| blue/dark | `--p-content-color`、`--p-text-color`（→ #e2e8f0 级浅色）、`--p-text-muted-color`（→ #94a3b8） |
| light/green | `--p-content-color`、`--p-text-color`（→ #334155 级深色）、`--p-text-muted-color` |
| 全部主题（可选） | `--p-datatable-*`、`--p-tag-*`、`--p-datepicker-*`（如映射表确认需要） |

> 注：P1 映射表以"验证环境实测每个 token 的消费者与达标色值"为准，避免过度注入。

## 六、P1 补充实证（2026-08，组件作用域 token 关键发现）

P1 实测（移除 B 阶段覆盖 + 注入 :root token 后）补充结论：

| 发现 | 实证 |
|---|---|
| **Aura 组件作用域 token 是解析后直接值** | `--p-datatable-header-cell-color` 在 `.p-datatable` 作用域 = `#334155`（非 `var(--p-content-color)` 引用），注入 :root 后 th/td 不变 → **DataTable 文字无法由根 token 覆盖** |
| **DatePicker 文字吃 :root content token** | 注入 `--p-content-color` 后 header/weekday/day 自动反白（T4）→ 可去补丁 |
| **Tag 的 Aura 默认色即达标** | 移除 B 阶段覆盖后 success tag = `#15803d` on 浅底 = 4.57:1（此前不达标是 style.css 旧覆盖 `var(--success)` 压过默认所致）→ **Tag 无需映射，B 覆盖可删** |
| **Input focus 不改文字色** | focus 前后 `--p-form-field-color` 不变 → 无需 focus 专项 token |
| **交互状态 token** | `--p-content-hover-color`/`--p-text-hover-color`/`--p-list-option-focus-color`/`--p-button-primary-hover-*` 需一并注入（避免 hover 变深） |

**映射表范围收敛（做减法）**：
- **根注入（:root，P2 实施）**：content/text/muted/hover/form-field/list-option/button-primary（blue/dark 浅色系；light/green 仅按钮）
- **保留 CSS 覆盖（P3 决策）**：DataTable 表头/正文（组件作用域直接值）、日历选中日（组件作用域 + Aura 默认不达标）——见 `web/src/theme/aura-token-map.ts` 的 `RETAINED_CSS_OVERRIDES`
- **Tag 覆盖可删除**（Aura 默认达标，做减法验证）

## 七、P2 实证（2026-08，运行时注入机制）

`useThemeSync` 新增 `syncAuraTextTokens()`（commit 37328b43）：

```ts
for (const token of ALL_MAPPED_TOKENS) root.style.removeProperty(token)  // 回退 Aura 默认
for (const [token, value] of Object.entries(AURA_TOKEN_MAP[themeId] ?? {})) root.style.setProperty(token, value)
```

| 验收项 | 实证结果 |
|---|---|
| 四主题注入 | light/green `--p-content-color`=#334155（无内联，回退默认）；blue/dark =#e2e8f0（注入）✅ |
| 连续切换 10 次（light↔dark） | 每次 dark #e2e8f0 / light 回退 #334155 且 inline=(none)，**无残留** ✅ |
| 组件反白 | 移除日历覆盖后 header/weekday/day 由注入 token 接管（blue #e2e8f0 13.48:1）✅ |
| 严禁空字符串 | 回退一律 `removeProperty`（空串会使 var() 解析失败）✅ |

## 八、P3 去补丁化实证（2026-08）

原子循环（移除 → audit → commit），每类独立 commit：

| commit | 移除类 | audit 结果 |
|---|---|---|
| b98d72a3 | 日历文字（header/weekday/标题/箭头/输入框/非选中日，-40 行） | 四主题 9.89-13.48 ✅ |
| abf65a2f | Tag 语义色（success/warn/info/danger，-23 行） | 四变体×四主题 4.52-5.3 ✅（green success 4.57 无同色系问题） |
| e2c94da4 | primary 按钮（默认+light，-29 行） | 四主题 6.29-9.22 ✅ |
| c3231475 | secondary 保留决策 + RETAINED 注释补全 | 全站复扫无回归 ✅ |

**量化收益**：style.css 880 → 808 行（-72）；`!important` 覆盖 24 → 8 处（全部为保留项）。

**最终保留覆盖（6 项，RETAINED 三要素注释）**：DataTable 表头/正文、Tag secondary、success/warning 按钮、secondary 按钮、日历选中日、日历边框/分隔线。

**剩余非范围项**：11 条既有 `--text-dim` 说明文字（dashboard widget 标签/页面描述），属 `--text-dim` 变量设计问题（后续"变量重设计"低优先项）。
