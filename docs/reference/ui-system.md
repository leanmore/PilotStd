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

---

## 十一、阶段三：表单输入控件（Input / Select / Checkbox / Toggle / DatePicker）

> 状态：**进行中**。规范（11.1–11.5）已定稿，`<App*>` 封装与存量替换按 `components/` → `views/` 两批推进。
> 门禁 `custom/no-raw-input` 当前为 `warn`，替换完成后升 `error`。

### 11.1 高度三档（与按钮同值、语义独立）

| 档位 | 高度令牌 | 值 | 字号 | 适用 |
|---|---|---|---|---|
| **L** | `--input-height-lg` | 40px | `--font-size-15` | 登录/引导页、单列表单 |
| **M** | `--input-height-md` | 34px | `--font-size-13` | 默认（绝大多数场景） |
| **S** | `--input-height-sm` | 28px | `--font-size-12` | 表格行内编辑、筛选栏、工具栏 |

- 水平内边距随档位取令牌（L `--space-16` / M `--space-12` / S `--space-8`），由 `App*` 组件内部决定，
  业务页不设置（页面只写布局，见 11.4）；
- 三档数值与按钮档位（`--btn-height-lg/md/sm`）**恰好相同**，但**语义独立**：
  输入框高度由「可点击的文本编辑区」决定，按钮高度由「点击目标」决定，二者会独立演化；
- **禁止**在输入控件上复用 `--btn-height-*`，也禁止反向把 `--input-height-*` 用在按钮上；
- 不允许出现 `height: 34px` / `padding: 9px 13px` 这类字面量（G-055 会拦）。

### 11.2 圆角

统一 `--ds-radius-md`（8px）。

- 输入框、下拉、日期选择器、开关容器一律同一圆角，**不再区分大小档**（尺寸档只改高度与字号）；
- **禁止新增引用**旧令牌 `--radius-sm`（6px）/ `--radius`（10px）/ `--radius-lg`（14px）；
  存量引用在替换批次内迁到 `--ds-radius-*`（见 4.1）；
- 禁止 `border-radius: 4px/6px` 字面量。

### 11.3 四态矩阵

| 状态 | 背景 | 边框 | 文字 | 其他 |
|---|---|---|---|---|
| **Default** | `--surface` | `1px solid var(--border)` | `--text` | `placeholder` 用 `--text-dim` |
| **Hover** | 同 Default（**不变**） | `1px solid var(--text-dim)` | `--text` | 仅提边框色，见下方理由 |
| **Focus** | 同 Default | `1px solid var(--primary)` | `--text` | `box-shadow: var(--focus-ring)`（统一外发光） |
| **Disabled** | `--disabled-bg` | `1px solid var(--border-light)` | `--disabled-text` | `cursor: not-allowed`；A-53 已接线 |

- **Hover 只提边框、不改底色**：表格行 hover 用的是 `--surface-raised` 底改色，输入框若也改底色，
  二者在同一行内会叠加出「双层高亮」，无法判断当前悬停的是行还是输入框。故输入框 hover **只**把
  `--border` 提到 `--text-dim`（同主题下对比度更高、可见但不高调），底色恒为 `--surface`。
- **Focus 统一外发光**：`border-color: var(--primary)` + `box-shadow: var(--focus-ring)` 是**一个组合**，
  由 `App*` 组件统一提供；**禁止各页自写**这两行（历史上有页面只写 `border-color`，键盘用户看不到焦点环）。
- **Disabled** 的 `--disabled-bg` / `--disabled-text` 由 `applyThemeToDom` 按主题注入（A-53 已接线），
  组件直接引用令牌，禁止写死灰值。

> 对比度约束：Default/Hover/Focus 的正文对 `--surface` 必须 ≥ 4.5:1；
> Disabled 文字对 `--disabled-bg` 允许放宽到 ≥ 3:1（由 `design-tokens.test.ts` 锁）。

### 11.4 禁止项

- **禁止原生 `<input>` / `<select>` / `<textarea>`**：一律用 `AppInput` / `AppSelect`；
  结构性用法（`type="file"` 的隐藏上传域、`type="radio"` 的表格单选、`type="hidden"` 等）走
  `<AppInput bare>` —— `bare` 零样式透传，保留原 class / 事件 / 可测试属性，**视觉零变化**；
- **禁止直接 import PrimeVue 输入组件**：`primevue/inputtext`、`primevue/select`、`primevue/checkbox`、
  `primevue/toggleswitch`、`primevue/datepicker`、`primevue/inputnumber`、`primevue/password`、
  `primevue/textarea`、`primevue/selectbutton`、`primevue/dropdown`；
- **禁止在业务页写输入框样式**：`.fi` / `.login-input` / `.p-inputtext` 之类的选择器不得在新代码出现，
  尺寸/圆角/四态一律由 `App*` 组件承担；页面只允许写**布局**（宽度、栅格、间距）。

### 11.5 组件契约

| 组件 | 底层 | 共有 props | 特有 props | v-model 语义 |
|---|---|---|---|---|
| `AppInput` | PrimeVue `InputText` / `Password` / `Textarea` / `InputNumber`（按 `type` 分叉） | `modelValue`、`size`(`l`/`m`/`s`)、`disabled`、`invalid`、`bare` | `type`、`placeholder`、`rows`、`toggleMask`、`showButtons`、`min`/`max`/`step`、`minFractionDigits`/`maxFractionDigits`、`inputClass`、`maxlength`、`id`、`name` | 见下方「`AppInput` 的 `type` 分叉」 |
| `AppSelect` | PrimeVue `Select` | 同上 | `options`、`optionLabel`、`optionValue`、`multiple`、`filter`、`placeholder`、`showClear` | 单选回传 `optionValue` 对应值；`multiple` 回传数组；emit 为泛型 `(value: T)`，`T` 由 `modelValue` 推断 |
| `AppSelectButton` | PrimeVue `SelectButton` | 同上 | `options`、`optionLabel`、`optionValue`、`optionDisabled`、`multiple` | **分段单选**（选项平铺可见），语义同 `AppSelect`；`allowEmpty` 保持 PrimeVue 默认 |
| `AppCheckbox` | PrimeVue `Checkbox` | 同上 | `binary`（默认 true）、`label`、`value`（非 binary 时为选项值） | `binary` 回传 `boolean`；非 binary 回传数组 |
| `AppToggle` | PrimeVue `ToggleSwitch` | 同上 | `trueValue`、`falseValue`（默认 `true`/`false`） | 回传 `trueValue`/`falseValue`；emit 为泛型 `(value: T)` |
| `AppDatePicker` | PrimeVue `DatePicker` | 同上 | `dateFormat`、`showTime`、`minDate`、`maxDate`、`selectionMode`、`placeholder` | 回传 `Date \| Date[] \| null`（随 `selectionMode`） |

**`AppInput` 的 `type` 分叉**（三组语义不同，不可混用）：

| 组 | `type` 取值 | 底层 | v-model 回传 | 说明 |
|---|---|---|---|---|
| 文本组 | `text`（默认）、`password` | `InputText`；`password` + `toggleMask` 时改用 `Password` | `string`（清空归一 `''`） | `toggleMask` 默认 `false`；开启后底层换 `Password`，多一个「显示明文」眼睛按钮 |
| 多行组 | `textarea` | `Textarea` | `string` | 高度由 `rows` + 内边距撑开，**不吃 `--input-height-*`**（固定高度会截断多行）；`min-height` 取 `--input-textarea-min-height` |
| 数字组 | `number` | `InputNumber` | **`number \| null`**（清空回 `null`，绝不回字符串） | `showButtons`/`min`/`max`/`step`/`minFractionDigits`/`maxFractionDigits` 显式透传；`inputClass` 落到内层 `.p-inputnumber-input` |
| 原生透传组 | `date`、`time`、`datetime-local`、`email`、`tel`、`url`、`search` | `InputText` | `string` | 用浏览器自带控件（如日期选择器），但**描边/高度/四态仍走 DS** |
| 结构性组 | `file`、`radio`、`hidden`、`checkbox` | 原生 `<input>` | 随控件 | **必须配 `bare`**，保留原生外观与 class，视觉零变化 |

- **`number` 清空的语义**：沿用 PrimeVue `InputNumber` 的 `allowEmpty` 默认（`true`），清空回 `null`。
  **必填校验属调用方责任**：`null < 0 === false` 会漏过范围校验，故业务侧须显式判 `== null`
  （示例见 `SettingsTabSites.vue` 的 `validate()`），否则 `null` 提交会被后端 Pydantic 拒成 422；
- **`class` vs `inputClass`**：`class` 落在组件根节点；`number` 分叉的根是 `span` 包装，
  要命中内层输入框请用 `inputClass`（走 `$attrs` 透传给 `InputNumber` 的 `inputClass`）；
- **泛型 emit**：`AppSelect` / `AppToggle` 用 `<script setup generic>`，`T` 由 `modelValue` 推断，
  用于消解 strictFunctionTypes 的参数逆变（`(v: string) => void` 不可赋给 `(v: unknown) => void`）。
  内部 handler 形参必须写 PrimeVue 原语的原始类型（如 `boolean`）再 `as T` 转出；
- `bare?: boolean` 是**统一逃生舱**（与 `AppButton` 的 `bare` 同义）：跳过 DS 样式，仅透传标签与属性；
  用于结构性控件与极端布局，**不是绕过门禁的手段** —— 仍必须走 `App*` 组件；
- 所有组件透传 `$attrs`（`aria-*`、`data-testid`、`name`、`@blur`、`@keyup.enter` 等），
  替换时这些属性必须原样保留（e2e 与登录流程依赖 `input[name=username]`）。

### 11.6 门禁

新增 ESLint 规则 **`custom/no-raw-input`**：

| 项 | 值 |
|---|---|
| 级别 | **`error`**（模块一替换完成后已升级；`138` 处存量归零） |
| 覆盖 | `src/**/*.{ts,vue}`，模板标签 + 脚本 import 两侧 |
| 豁免 | `src/components/ui/App*.vue`（封装点）、`src/main.ts`（PrimeVue 全局注册点）、`*.test.ts` / `*.spec.ts`、路径含 `/e2e/` |
| 单测 | `eslint-plugin-custom/rules/no-raw-input.test.js`（RuleTester） |

**存量基线（2026-11-22，warn 落地时）**：`138` 处命中、分布在 `27` 个文件：

| 控件类型 | 命中 | 控件类型 | 命中 |
|---|---:|---|---:|
| PrimeVue import | 31 | PrimeVue `<Select>`/`<Dropdown>` | 7 |
| 原生 `<input>` | 23 | 原生 `<select>` | 6 |
| PrimeVue `<InputText>` | 21 | PrimeVue `<Checkbox>` | 5 |
| PrimeVue `<InputNumber>` | 16 | PrimeVue `<Textarea>` | 4 |
| PrimeVue `<ToggleSwitch>` | 15 | PrimeVue `<SelectButton>` | 4 |
| PrimeVue `<Password>` | 3 | PrimeVue `<DatePicker>` | 2 |
| 原生 `<textarea>` | 1 | | |

> 升级验证方式（与 10.5 同口径）：临时放一个含原生 `<input>` 的组件 → `lint` 报 **1 error** 并 exit 1；
> 删除后恢复 PASS。
>
> **2026-11-22 升级实录**：探针文件 `src/views/__GateProbe.vue` 同时含原生 `<input>`、原生 `<select>`、
> PrimeVue `<InputText>` 与 `import 'primevue/inputtext'` → `lint` 报 **4 error**、exit 1，
> 四条提示分别指向 `AppInput` / `AppSelect`；删除后 `lint` 恢复 `0 error`、exit 0。

### 11.7 验收清单（阶段三）

- [x] `--input-height-lg/md/sm` 令牌落地（`design-tokens.css`）
- [x] A-53 接线：`--disabled-bg` / `--disabled-text` 由 `applyThemeToDom` 注入
- [x] `AppInput` / `AppSelect` / `AppSelectButton` / `AppCheckbox` / `AppToggle` / `AppDatePicker` + 单测
- [x] `eslint-plugin-custom/rules/no-raw-input.js` + RuleTester 单测
- [x] 本规范章节（11.1–11.6）
- [x] `components/` 替换完成（`no-raw-input` 归零）
- [x] `views/` 替换完成（`no-raw-input` 归零）
- [x] 规则升 `error`（反证：4 error / exit 1）

### 11.8 模块一交付台账（2026-11-22 完成）

**Web 端：`138` 处 → `0`**

| 批次 | 范围 | 主要替换 |
|---|---|---|
| C1 | `FileMonitor` / `UnifiedFilterBar` / `AppCalendar` | 4 `AppInput` + 4 `AppToggle` + 1 `AppDatePicker` |
| C2 | `DynamicSettingField` / `RouteDebugPanel` | 6 `AppInput` + 2 `AppSelect` + 1 `AppInput type=textarea` |
| C3 | `NotificationConfig` / `WechatTrustIP` | 11 `AppInput` + 3 `AppToggle` + 3 `AppCheckbox` + 1 `AppSelect` + 3 `AppSelectButton`（新封装） |
| C4 | `ValidityConfig` / `CacheManager` / `SettingsTabAppearanceMixed` / `TaskManager` | 10 `App*` + 1 `AppInput bare type=radio` + 1 `AppInput bare type=file` + 1 `AppSelectButton` |
| D1 | `LoginView` / `RegisterView` / `SettingsView` / `TaskView` / `OrganizeView` | 8 `App*`（含 `name="username"` 契约保持） |
| D2 | 11 个 views（含 `views/settings/`） | 39 `App*` 控件 |

**替换过程中修掉的真实缺陷**（都有单测或探针复现）：

1. **`FileMonitor.vue` 是全仓唯一的 Options API SFC** —— `<script>` 里 import 的组件不会自动注册，
   只换标签名会在生产渲染成未知元素（测试靠 stubs 兜住、静默失效）。补 `components: { ... }` 显式注册。
2. **`AppInput` 无 PrimeVue 插件时崩溃** —— `@primevue/core` 的 `$variant` 在 `variant` 为 null 时
   无条件读 `$primevue.config`；只测文案的 i18n 测试不装插件 → `TypeError`。四个分叉统一传
   `variant="outlined"` 短路。
3. **`textarea` 被压成单行** —— 根节点挂 `app-input--${size}` 时其 `height: --input-height-*`
   压过 `min-height`。textarea 分叉不挂尺寸类。
4. **`ValidityConfig` 数字联动静默失效** —— 换成 `:model-value` + handler 后新值没写回 `config`，
   用户改 T/F/P 全不生效（现有单测测不出，因为它们直接改 `vm.config`）。补 `writeNumber()` 先写回再联动。
5. **`CacheManager` radio 的 v-model 把 number 变 string** —— 原生 `v-model` 走 `vModelRadio` 保 number，
   `AppInput` 单行走 DOM 事件回传字符串，会把 `maxSize` 变成 `"50"` 再 PUT 给后端。
   改 `:checked` + `@change` 闭包保 number。
6. **`SettingsTabSites` 清空数字字段漏校验** —— `null < 0 === false` 会放过空值，最终被后端 422 拒。
   在 `validate()` 补 `== null` 必填判断（并补三语 i18n 键 `sites.validation.number_required`）。

**Win 端**：`BaseInput` / `BaseSelect` 见 §12（模块一-E 交付）。

