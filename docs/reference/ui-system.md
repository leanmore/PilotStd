# UI 组件与视觉规范（跨端设计系统 DS · 阶段一）

> 适用端：**Web（Vue3 + PrimeVue）**、**Win（PyQt6）**。
> 状态：阶段一（规范 + 骨架），**未批量替换现有业务代码**。
> 唯一数据源：`web/src/styles/design-tokens.css`（尺度/圆角/字重/行高）与
> `web/src/config/themes.ts`（四主题颜色）。Win 端由 `scripts/gen_win_tokens.py` 生成，禁止手写色值。

---

## 一、为什么要有这份规范

现状（2026-11-22 取证）：

- 按钮圆角有 `4px`（`QMenu::item`、`QPushButton` 的 `border-radius: 6px` 与 `--radius: 10px` 并存）三套值；
- 危险操作分裂：`TaskView` 用实心橙、`SettingsView` 用空心红、部分页面用 `severity="danger"` 实心红；
- 图标与文字间距各页自定（`gap: 4/6/8px` 混杂）；
- Win 端 `pilotstd/ui/themes.py` 的 `COLOR_SCHEMES` 是**第二份色值真相**，与 `themes.ts` 已出现漂移风险。

本规范的目标：**同一语义在两端只有一种实现**，且样式值只能来自令牌。

---

## 二、按钮层级（Button Hierarchy）

四种层级，语义互斥，不允许自创第五种。所有值均来自令牌。

### 2.1 定义

| 层级 | 用途 | 背景 | 文字 | 边框 |
|---|---|---|---|---|
| **Primary** | 页面/弹窗的**主操作**（每屏最多 1 个） | `--primary-fill` | `--text-on-primary` | 无 |
| **Secondary** | 次操作（刷新、导出、取消以外的辅助动作） | `--surface` | `--text` | `1px solid var(--border)` |
| **Danger** | **破坏性/不可逆**操作（删除、清空、覆盖） | `--danger` | `--text-on-primary` | 无 |
| **Ghost** | 低强调（取消、关闭、工具栏图标） | `transparent` | `--text-secondary` | 无 |

### 2.2 状态矩阵

| 状态 | Primary | Secondary | Danger | Ghost |
|---|---|---|---|---|
| 默认 | bg `--primary-fill` | bg `--surface` / border `--border` | bg `--danger` | bg `transparent` / text `--text-secondary` |
| Hover | bg `--primary-fill-hover` | bg `--surface-raised` | bg `--danger-hover`（无此令牌时用 `--danger-text` 加深） | bg `--surface-raised` |
| Active | 同 Hover + `transform: translateY(0)` | 同 Hover | 同 Hover | 同 Hover |
| Disabled | bg `--disabled-bg` / text `--disabled-text` / `cursor: not-allowed` | 同左 | 同左 | 同左 |
| Focus | `outline: 2px solid var(--focus-ring)` + `outline-offset: 2px` | 同左 | 同左 | 同左 |

> **对比度约束**：Primary/Danger 的文字对各自背景必须 ≥ 4.5:1（由 `a11y-contrast.test.ts` 锁）；
> Secondary 的文字对 `--surface` 必须 ≥ 4.5:1。

### 2.3 禁止项

- 禁止用 `severity="danger"` 之外的**实心橙**表示危险（历史遗留，分批替换时统一到 Danger）；
- 禁止「危险操作」用 Primary 样式（视觉上无法与主操作区分）；
- 同一容器内不得出现两个 Primary。

---

## 三、尺寸规格（Size Scale）

| 档位 | 高度 | 水平 Padding | 字号 | 图标尺寸 | 适用 |
|---|---|---|---|---|---|
| **L** | `--btn-height-lg`（40px） | `--space-20` | `--font-size-15` | `--size-20` | 登录/引导页主按钮 |
| **M** | `--btn-height-md`（34px） | `--space-16` | `--font-size-13` | `--size-16` | 默认（绝大多数场景） |
| **S** | `--btn-height-sm`（28px） | `--space-12` | `--font-size-12` | `--size-14` | 表格行内、工具栏 |

- 高度用 `--btn-height-*`（新增令牌，见第五节），**不复用 `--space-*`**（语义不同）。
- 不允许出现 `height: 34px` 这类字面量（G-055 会拦）。

---

## 四、圆角与图标

### 4.1 圆角

统一到 `--ds-radius-*` 家族：

| 元素 | 令牌 | 值 |
|---|---|---|
| 输入框 / 小按钮（S） | `--ds-radius-sm` | 6px |
| 按钮（M/L）/ 卡片 | `--ds-radius-md` | 8px |
| 弹窗 / 面板 | `--ds-radius-lg` | 12px |
| 徽标 / 状态点容器 | `--ds-radius-pill` | 999px |

- **旧的 `--radius`（10px）/ `--radius-sm`（6px）/ `--radius-lg`（14px）冻结**：不再新增引用，替换时迁到 `--ds-radius-*`；
- 禁止再出现 `border-radius: 4px` / `6px` 字面量。

### 4.2 图标

| 项 | 规则 |
|---|---|
| 图标与文字间距 | `--space-8`（紧凑场景 `--space-6`） |
| 图标尺寸 | 随尺寸档：S `--size-14`、M `--size-16`、L `--size-20` |
| 图标颜色 | 继承文字色（`currentColor`），不单独设色 |
| 仅图标按钮 | 必须带 `aria-label`；尺寸 = 高度 × 高度（正方形） |

---

## 五、跨端 Token 同步机制

### 5.1 单一真相与生成方向

```
web/src/styles/design-tokens.css   ← 唯一真相（尺度/圆角/字重/行高）
web/src/config/themes.ts           ← 唯一真相（四主题颜色）
            │
            ▼  scripts/gen_win_tokens.py（只读生成，不手改产物）
pilotstd/ui/tokens_generated.py    ← Win 端令牌（颜色 + 尺度，四主题字典）
            │
            ▼  pilotstd/ui/widgets/base_button.py 读取
QSS 字符串（BaseButton / 全局样式）
```

### 5.2 生成脚本约束

- **只读源、只写产物**：脚本不修改 `design-tokens.css` / `themes.ts`；
- **确定性**：同一输入两次生成逐字节一致（排序固定），便于 diff 复核；
- **缺失即失败**：源文件读不到、令牌数为 0、解析出非法值时 `exit 1`，绝不生成空文件；
- **不自动接线**：产物入库，但**不自动 import**；由 `BaseButton` 显式引用（避免启动期耦合）。

### 5.3 覆盖范围（阶段一）

| 类别 | 是否生成 | 说明 |
|---|---|---|
| 颜色（四主题） | ✅ | 从 `themes.ts` 解析 `THEMES` 对象 |
| 间距 / 字号 / 行高 / 字重 / 圆角 / 尺寸 | ✅ | 从 `design-tokens.css` 的 `:root` 解析 |
| 阴影 / 渐变 | ❌ | 跨端渲染差异大，阶段二再评估 |
| 动画时长 | ❌ | 同上 |

### 5.4 一致性守护

- `tests/test_win_tokens_sync.py`：重新生成并与入库产物比对，不一致即失败（防"改了 Web 忘了同步 Win"）；
- CI 同批跑（`check_all.sh --fast`）。

---

## 六、Web 端封装：`<AppButton>`

### 6.1 契约

```vue
<AppButton type="primary|secondary|danger|ghost" size="l|m|s" :loading :disabled :block icon="pi pi-x" label="..." @click />
```

| Prop | 取值 | 默认 |
|---|---|---|
| `type` | `primary` / `secondary` / `danger` / `ghost` | `secondary` |
| `size` | `l` / `m` / `s` | `m` |
| `loading` / `disabled` | boolean | `false` |
| `block` | boolean（撑满父容器） | `false` |
| `icon` | PrimeIcons 类名 | `''` |

- 内部**只用令牌**，不写任何字面量；
- 透传 `$attrs`（`aria-*`、`data-*`、`@click` 等）；
- `loading` 时禁用点击并显示 `pi pi-spin pi-spinner`。

### 6.2 门禁：禁止原生按钮

新增 ESLint 规则 `custom/no-raw-button`：

- **禁止**业务代码出现原生 `<button>` 标签；
- **禁止**直接 import / 使用 PrimeVue 的 `<Button>`；
- 豁免：`src/components/ui/AppButton.vue` 自身、测试文件、`*.stories.*`。

> 阶段一：规则以 `warn` 落地并登记存量数量；分批替换完成后升 `error`。
> 原因：一次性全量替换会与"不破坏现有功能"冲突。

---

## 七、Win 端对齐：`BaseButton`

```python
from pilotstd.ui.widgets.base_button import BaseButton

btn = BaseButton("开始抓取", kind="primary", size="m")
btn = BaseButton("删除", kind="danger")
btn = BaseButton("取消", kind="ghost", size="s")
```

- `kind` 对应 Web 的 `type`；`size` 对应 `l/m/s`；
- 内部从 `pilotstd/ui/tokens_generated.py` 取色与尺寸，**不读 `themes.py` 的 `COLOR_SCHEMES`**；
- 通过 `setProperty("variant", ...)` + QSS 选择器实现四层级，避免每处手写样式表；
- 阶段一：新增类，不替换现有 `QPushButton` 调用点。

---

## 八、迁移路径（阶段二起，本阶段不做）

1. 先替换 **Danger** 类按钮（当前最分裂）；
2. 再替换 Primary（每屏 1 个，收益最高）；
3. 最后批量 Ghost/Secondary；
4. 每批跑四件套 + G-055 + 目视核对；ESLint 规则在批末升 `error`。

---

## 九、验收清单（阶段一）

- [x] 本规范文档
- [x] `scripts/gen_win_tokens.py` + 产物 `pilotstd/ui/tokens_generated.py`
- [x] `web/src/components/ui/AppButton.vue` + 单测
- [x] `eslint-plugin-custom/rules/no-raw-button.js` + RuleTester 单测
- [x] `pilotstd/ui/widgets/base_button.py` + 单测
- [x] `tests/test_win_tokens_sync.py`（产物与源一致）
- [ ] 业务代码批量替换（**阶段二**，待确认）

---

## 十、阶段二：存量替换台账（2026-11-22 完成）

### 10.1 Web 端（142 处 → 0）

| 批次 | 范围 | 处数 | 结果 |
|---|---|---:|---|
| 1 | Danger 语义（清理/删除/停止/取消） | 10 | 统一 `type="danger"`，消除实心橙 vs 空心红分裂 |
| 2 | 非 text 的 PrimeVue Button（主/次操作） | 51 | 按 severity 映射到 primary/secondary/danger |
| 3 | text 按钮 + 全部原生 `<button>` | 81 | text → `type="ghost"`；原生按语义分类处理 |

**最终账本**：`pnpm lint` 的 `custom/no-raw-button` 命中 **0**（起始 142）。

### 10.2 AppButton 新增能力（替换过程中补齐）

| Prop | 用途 | 来源 |
|---|---|---|
| `outlined` | 空心（红/主色描边） | PrimeVue `outlined` |
| `text` | 纯文字按钮 | PrimeVue `text` |
| `rounded` | 胶囊圆角 | PrimeVue `rounded` |
| `badge` / `badgeSeverity` | 角标（未读数） | PrimeVue `badge` |
| `bare` | 零样式透传，外观交给宿主 class | 结构性控件专用 |

### 10.3 原生 `<button>` 的处置

18 处原生按钮中：

- **4 处**为普通操作按钮（调试、加载全部、清理日志×2）→ 直接换 `AppButton` 的对应层级；
- **14 处**为结构性控件（顶栏图标按钮、浮动拖拽按钮、`role="menuitem"` 菜单项、子标签/标签页切换、
  侧栏折叠把手、卡片删除角标）→ 换 `AppButton` + **`bare`**，保留原 class 与全部事件/无障碍属性，**视觉零变化**。

> `bare` 不是"绕过门禁"，而是把「结构性控件」与「按钮层级」解耦：组件统一、样式归宿主。
> 若将来这些控件需要统一外观，改宿主 class 即可，无需再动标签。

### 10.4 Win 端（46 处 → 0）

`QPushButton(...)` 全部替换为 `BaseButton(...)`，按语义补 `kind`：

| kind | 场景 | 处数 |
|---|---|---:|
| `primary` | 确定/开始/查询/下载/保存/导入/导出/立即… | 20 |
| `secondary` | 浏览/刷新/编辑/复制… | 15 |
| `ghost` | 取消/关闭/返回/清除完成 | 9 |
| `danger` | 删除/清理 | 2 |

样式来源：`pilotstd/ui/tokens_generated.py`（由 `scripts/gen_win_tokens.py` 从 Web 源生成），
**不使用** `themes.py` 的 `COLOR_SCHEMES`。

### 10.5 门禁升级

`eslint.config.js` 的 `custom/no-raw-button` 已由 `warn` 升为 **`error`**。
验证方式：临时放一个含原生 `<button>` 的组件 → `lint` 报 **1 error** 并 exit 1；删除后恢复 PASS。

### 10.6 遗留

- **A-53**：`disabledBg`/`disabledText` 仍是死键（`applyThemeToDom` 未接线）。`AppButton` 的禁用态
  暂用 `--border-light` + `--text-dim` 替代；接线后可直接替换，不影响其它规则。
