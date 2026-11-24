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

**Win 端**：`BaseInput` / `BaseSelect` 见 `docs/architecture/modules/ui.md` 的
「输入控件统一：BaseInput / BaseSelect」小节（模块一-E 交付，2026-11-22）。要点：

- 与 Web 一一对应：`size` l/m/s 映射 `--input-height-*`，圆角 `--ds-radius-md`，
  四态（default/hover/focus/disabled）全部取自 `tokens_generated.py`，缺令牌抛 `KeyError`；
- A-53 Win 侧同步收口：`BaseButton` / `BaseInput` / `BaseSelect` 的禁用态统一消费
  `disabledBg` / `disabledText`，不再用 `borderLight` + `textDim` 顶替；
- **QSS 没有 `box-shadow`**，故聚焦态用「描边加粗到 2px + 主色」等效 Web 的外发光，
  并按 `min-height -2 / padding -1` 做等高换算，保证四态外框总高恒等于高度令牌
  （否则表单控件获得焦点时会跳高、把下方元素顶下去）；
- 两个 Qt 侧实测坑：`QComboBox` 在应用级 QSS 下首次 `sizeHint()` 会返回未套样式的高度
  （需 `ensurePolished()` + `updateGeometry()`）；placeholder 调色板必须在 `ensurePolished()`
  **之后**设置，否则被 QSS 的 `color` 重建覆盖。

---

## 十二、阶段三：数据表格与弹窗（Table / DataGrid / Dialog）

> 状态：**进行中**。规范（12.1–12.4）已定稿，`<AppTable>` / `<AppDialog>` 封装与存量替换
> 按 `components/` → `views/` 两批推进。
> 门禁 `custom/no-raw-table` 当前为 `warn`（存量基线 36 处 / 17 文件），替换完成后升 `error`。

### 12.1 表格规范

统一由 `<AppTable>` 承担，业务页只写「哪些列 + 什么数据 + 布局宽度」，不写表头/斑马纹/边框样式。

| 部位 | 令牌 / 值 | 说明 |
|---|---|---|
| 表头背景 | `--surface-raised` | 与内容区（`--surface`）拉开一档，形成「表头带」 |
| 表头字色 | `--text` | **不是** `--text-secondary` / `--text-dim`，见下方对比度理由 |
| 表头字号 | `--font-size-11` | 比正文小一档，靠字重与大小写补层级 |
| 表头字重 | `--font-weight-semibold` | 600 |
| 表头大小写 | `text-transform: uppercase` | 配合字距做「标签化」处理 |
| 表头字距 | `0.6px`（结构性字面量，登记进 G-055 基线 `ds-skeleton` 组） | 小字号全大写时字距必须放开，否则糊成一片 |
| 表头内边距 | `--space-10` / `--space-14` | 上下 10px、左右 14px |
| 单元格边框 | `--border-light` | 行分隔用最浅一档，避免整表被线条切碎 |
| 行内边距 / 字号 | `--space-9` / `--space-14`；`--font-size-13` | 上下 9px、左右 14px |
| 表格圆角 | `--ds-radius-md`（容器上）+ `overflow: hidden` | 旧 `--radius`（10px）冻结，按 4.1 收敛到 8px；圆角靠容器裁剪表头四角 |
| 普通行底色 | `--surface` | 与表头 `--surface-raised` 形成层级 |
| 行 hover | `--selected` | 主色 8% 透明叠底，与斑马纹是两级信号 |
| 斑马纹（`:nth-child(even)`） | `--surface-raised` | 极浅抬升面；**不新增 `--table-stripe`**，见下方说明 |
| 分页器 | 背景 `--surface` / 边框 `--border` / 页码圆角 `--radius-sm` / 页码尺寸 32×32 | **刻意留在 `style.css`**（C 类 RETAINED 段）：分页器是 PrimeVue `Paginator` 的内部结构，与表格本体解耦，放全局段对「尚未迁移的直接 `<DataTable>`」同样生效；且 32px 在 `design-tokens.css` 里没有独立语义令牌（唯一同值是 `--icon-tile-sm`「仪表盘图标方块」，挪用属语义错配）。当前页 `--primary-fill` + `#fff` |

**表头字色为什么是 `--text` 而不是 `--text-secondary`**（RETAINED，勿改）：

> Aura 的组件作用域 token（`--p-datatable-header-cell-color` 等）解析后是**直接值** `#334155`，
> 在 root 级注入 `--p-content-color` 覆盖不到（P1 实证）。改用 `--text-dim` 时浅色主题实测仅
> **2.4–2.6:1**，不满足 WCAG AA；改用 `--text` 后 ≈**7:1**（浅色深字 / 深色浅字自适应）。
> 层级感由「加粗 + 大写 + 小字号 + 字距」承担，不靠降亮度。
> 依据：`docs/technical-debt.md`（Tech-Debt #8）。

**为什么斑马纹用 `--surface-raised`、hover 用 `--selected`（且不新增 `--table-stripe` 令牌）**：

1. **两级信号必须可分辨**：斑马纹是「可扫读底色」（静态、常驻），hover 是「当前指向的那一行」
   （动态、瞬时）。两者若同用 `--selected`，hover 行会与相邻的斑马行**同色**，
   「当前悬停哪一行」反而不可辨 —— 与 11.3 里「输入框 hover 不改底色、避免与表格行 hover
   叠加成双层高亮」是同一条取舍逻辑。
2. **`--surface-raised` 本就是现有观感**：迁移前 `style.css` 的
   `.p-datatable-tbody>tr:nth-child(even)` 用的就是 `--surface-raised`，本轮目标是
   「视觉等价地令牌化」而非重新设计，改用它以外的值会引入新观感。
3. **不新增 `--table-stripe` 的理由**：新增颜色令牌必须同时写进 `themes.ts` 的四套主题、
   `applyThemeToDom` 的映射表与 `style.css` 的 `:root` 默认值，并触发 `design-tokens.test.ts`
   的「映射表覆盖全部颜色键」断言，还要同步 Win 端 `gen_win_tokens.py` 的产物。
   现有两个令牌已能表达这两级信号，为一个没有独立视觉诉求的用途付这份成本不划算。
4. **反例留档**：若将来产品要求「斑马纹必须中性灰、且与 hover 同色系」，那才需要新增
   `--table-stripe` 并同步四主题，而不是在本节改口径。

- 斑马纹靠 PrimeVue 的 `stripedRows`（`AppTable` 透传），**不要**在业务页写
  `:nth-child(even)` 选择器；
- 行 hover 的过渡用 `--transition`（0.2s），不要各页自定义时长；
- 空数据提示（`#empty` 插槽）文字用 `--text-dim`、上下 `--space-32`、居中、`--font-size-13`；
- **行内可编辑单元格**（如 `AnnounceDetail` 的可编辑列）用 `AppInput size="s"`，
  不要为了塞进表格而自降高度写死像素。

> **`style.css` 的 `.p-datatable` 段与 `AppTable` 的关系**：该段**保留**，服务尚未迁移的直接
> `<DataTable>` 用法（如 `TaskManager` 的两张表），已同步令牌化为与 `AppTable` **逐条等价**的值
> （唯一差异是圆角：`--radius` 10px → `--ds-radius-md` 8px）。`AppTable` 渲染时组件内 `:deep()`
> 因多一个 `.app-table` 类而特异性更高，覆盖结果一致，**不存在两套样式打架**。
> 模块二-B 迁移完成后该段可删。

### 12.2 弹窗规范

统一由 `<AppDialog>` 承担。

| 部位 | 令牌 / 值 | 说明 |
|---|---|---|
| 遮罩层 | **不新增令牌**，沿用 PrimeVue Aura 的 `mask.background`（`--p-mask-background`）：浅色主题（light / green）`rgba(0, 0, 0, 0.4)`、深色主题（dark / blue）`rgba(0, 0, 0, 0.6)` | 该值来自 Aura preset，**不在本仓 `:root`**，本仓不覆盖；见下方说明 |
| 弹窗圆角 | `--ds-radius-lg`（12px） | 冻结的旧 `--radius-lg`（14px）不得新增引用 |
| 弹窗背景 / 边框 | `--surface` + `1px solid var(--border)` | 与卡片同口径 |
| 阴影 | `--shadow-lg` | 与 PrimeVue 默认 shadow 二选一，取 DS 值 |
| header 内边距 | `--space-18` / `--space-20`（上下 18px、左右 20px） | 迁移前是 `18px 22px` 字面量；间距档位表里**没有 22**（1/2/3/4/6/7/8/9/10/12/14/16/18/20/24/30/32/40/44），故水平收敛到最近的 `--space-20`（视觉差 2px 不可辨），竖直保留精确的 `--space-18` |
| content 内边距 | 同 header（`--space-18` / `--space-20`） | header/content 左右必须对齐，否则标题与正文错位 |
| header 分隔线 | `1px solid var(--border)`（仅 header 下沿） | content 自身不加边框；footer 沿用 PrimeVue 默认（见下行） |
| header 标题 | 色 `--text-heading`、字重 `--font-weight-semibold` | 比正文高一档亮度 |
| 关闭按钮位置 | 右上角，由 PrimeVue 的 `header-actions` 区承载（Aura 默认即在 header 右侧） | **不要**用绝对定位自造；`#closebutton` 插槽可整体替换 |
| 关闭按钮尺寸 | **只收敛图标字号**到 `--size-20`，色 `--text-secondary`，hover 转 `--text` | 作用于 `.p-dialog-close-button .p-button-icon`，**刻意不设按钮本体 width/height**：Aura 的关闭按钮是 text+rounded 图标按钮，硬设 20×20 会压没内边距、把点击热区缩到 20px（< WCAG 2.5.8 的 24px 最小目标）；只改图标字号既满足「右上角 20px 图标」口径，又保住热区 |
| footer | **不在封装内定制**，沿用 PrimeVue 默认（内容右对齐、按钮间距 `0.5rem`、上无分隔线） | 主操作在右（与 `AppButton` 层级一致）；需要分隔线时由调用方在 `#footer` 内自行加 |

**遮罩层为什么这轮不新增 `--overlay-backdrop`**：

- 现有视觉直接来自 Aura 的 `mask.background`（浅色 0.4 / 深色 0.6），`web/src/style.css` 与
  `theme.css` 均**没有**覆盖 `.p-overlay-mask`，即当前观感就是 Aura 默认值，没有「两套值打架」问题；
- 新增颜色令牌的连带成本是四主题各写一份 + `applyThemeToDom` 接线 + `design-tokens.test.ts` 的
  映射覆盖断言 + `scripts/gen_win_tokens.py` 的产物同步（Win 端 `BaseDialog` 也要吃同一份），
  而本轮**没有明确的视觉诉求**（不是「遮罩太黑看不清」这类具体缺陷）；
- 因此裁定：**本轮不新增**。若将来确需调整，按 5.1 的单一真相流程新增 `--overlay-backdrop`，
  同批改四主题 + `applyThemeToDom` + `style.css :root`，并把 Win 端产物一起重生成。

- 业务页只传 `v-model:visible` / `header` / `:style="{ width: 'Npx' }"` 这类**布局与语义**参数，
  圆角、内边距、分隔线、关闭按钮位置一律不写；
- 宽度用 `:style="{ width: 'Npx' }"` 是既有约定（存量 7 个弹窗都这么写），`AppDialog` 必须透传
  `style`/`class`，替换时**宽度语义原样保留**；
- `dismissableMask` **默认 `false`**（与 PrimeVue 一致）：破坏性操作确认弹窗**不要**开；
  只有「随便点哪都能关」的信息型弹窗才显式开；
- `closable` / `draggable` 默认 `true`（PrimeVue 默认），需要锁死时显式传 `false`；
- `header` 类型是 `string`（默认 `undefined`）：PrimeVue 的 `d.ts` 是 `string | undefined`，
  传 `null` 会在 `vue-tsc` 报 TS2322；`#header` 插槽可完全接管标题区。

> **`style.css` 的 `.p-dialog` 段与 `AppDialog` 的关系**：该段**保留**，服务尚未迁移的直接
> `<Dialog>` 用法（存量 7 处），已同步令牌化为与 `AppDialog` **逐条等价**的值（唯一差异是圆角：
> `--radius-lg` 14px → `--ds-radius-lg` 12px）。`AppDialog` 的样式块**不带 `scoped`**（内容经
> `<Portal>` teleport 到 body，scoped 的 `[data-v-*]` 落不到 teleport 后的节点上），改用
> `html .app-dialog` 前缀收口并压过 `style.css` 的 `.p-dialog` 段，**不存在两套样式打架**。
> 模块二-B 迁移完成后该段可删。

### 12.3 禁止项

- **禁止手写原生 `<table>` 做数据表**：表头/斑马纹/hover/边框/圆角/分页器一律由 `AppTable` 提供。
  历史遗留的 6 处手写表格（`DownloadQueue` / `NotificationLogsView`×2 / `ValidityConfig` /
  `AdapterStatusCard` / `QueryHistory`）属模块二-B 的替换目标，`custom/no-raw-table` 会命中；
  `QueryHistory` 的手写表格是本轮明确要替换的对象（**预期命中，不是误伤**）。
  > 例外：`AppTable` 内部**不使用** `<table>` —— PrimeVue 自己渲染 `<table>`，封装层不出现该标签，
  > 所以本规则与 `AppTable` 实现不冲突。
- **禁止直接 import / 使用 PrimeVue 表格与弹窗组件**：
  `primevue/datatable`、`primevue/treetable`、`primevue/datagrid`、`primevue/dialog`、
  `primevue/confirmdialog`、`primevue/dynamicdialog`；
- **禁止在业务页写表格/弹窗样式**：`.data-table` / `.log-table` / `.adapter-table` /
  `.p-datatable` / `.p-dialog` 之类的选择器不得在新代码出现，视觉一律由 `AppTable`/`AppDialog` 承担；
  页面只允许写**布局**（宽度、栅格、间距、`min-width`）；
- **`primevue/column` 不在禁止清单内**：`<Column>` 是 `AppTable` 默认插槽的配套子组件，
  业务页照常 `import Column from 'primevue/column'` 使用；
- **`bare` 不是绕过门禁的手段**：树形表格 / 合并单元格 / `DataGrid` 语义走 `<AppTable bare>`
  或 `<AppDialog bare>`（零样式透传），但**仍必须经 `App*` 组件**，不得回到 PrimeVue 原语。

### 12.4 组件契约

| 组件 | 底层 | 显式 props（含默认值） | `$attrs` 透传 | 透传的 slots |
|---|---|---|---|---|
| `AppTable` | PrimeVue `DataTable` | 仅 `bare: boolean = false` | `inheritAttrs: false` + `v-bind="$attrs"`：`:value`、`paginator`、`:rows`、`:totalRecords`、`stripedRows`、`:loading`、`dataKey`、`selectionMode`、`v-model:selection`、`expandedRows`、`editMode`、`:scrollHeight`、`size`、`class`、`@page` / `@sort` / `@rowSelect` / `@cell-edit-complete` … 全部原样透传 | 按 `$slots` 动态全量转发：默认插槽（放 `<Column>`）、`#header`、`#empty`、`#footer`、`#groupheader`、`#expansion`、`#loading`、`#paginatorstart` / `#paginatorend` 及任何未列举的具名插槽 |
| `AppDialog` | PrimeVue `Dialog` | `visible: boolean = false`、`header: string = undefined`、`modal: boolean = false`、`dismissableMask: boolean = false`、`closable: boolean = true`、`draggable: boolean = true`、`bare: boolean = false`；emits：`update:visible` / `show` / `hide` | `inheritAttrs: false` + `v-bind="$attrs"`：`:style`（宽度约定）、`class`、`maximizable`、`position`、`appendTo`、`contentStyle` / `contentClass`、`breakpoints`、`blockScroll`、`closeOnEscape`、`baseZIndex`、`pt` … 全部原样透传 | 按 `$slots` 动态全量转发：默认插槽（内容）、`#header`、`#footer`、`#container`、`#closebutton`、`#maximizebutton`、`#closeicon`、`#maximizeicon` 及任何未列举的具名插槽 |

> `header` 的类型刻意是 `string`（**不是** `string \| null`）：PrimeVue `Dialog` 的 `d.ts` 声明为
> `header?: string \| undefined`，传 `null` 会在 `vue-tsc` 阶段报 **TS2322**。`#header` 插槽可完全接管标题区。

**为什么 `AppTable` 只显式声明 `bare` 一个 prop**：`DataTable` 的 props/事件有 80+ 个，
逐条声明等于抄一遍 PrimeVue 的 `d.ts`，漏一个就静默失效（值落到 DOM attribute 上、不报错、
单测也测不到），维护成本远高于收益。故全量 `$attrs` 透传，语义与直接用 PrimeVue `DataTable`
**完全同构**，迁移时只改标签名（`<DataTable>` → `<AppTable>`），props/事件一个都不用动。

**为什么 `AppDialog` 要显式声明 7 个 prop 与 3 个 emit**：这 7 个同时是 `v-model` 与 a11y 的
语义锚点，声明出来才有类型提示与契约可写；`update:visible` 若只透传，声明式 `emits` 会把监听器
从 `$attrs` 里摘掉，必须手动转发（`v-model:visible` 依赖它）；`show` / `hide` 是业务侧关闭时
清理状态的钩子（`TaskManager` 用 `@hide="detailTask = null"`）。其余事件继续走 `$attrs`。

**`bare` 逃生舱（两个组件同义，与 `AppButton` / `AppInput` 的 `bare` 一致）**：

| 项 | `bare: false`（默认） | `bare: true` |
|---|---|---|
| 样式 | 施加 12.1 / 12.2 全部 DS 视觉（表头、斑马纹、hover、圆角、内边距、分隔线…） | **零样式**：走 PrimeVue `:unstyled="bare"`，连 `p-datatable` / `p-dialog` / `p-overlay-mask` 类名都不生成，外观（含遮罩）全部交给宿主 |
| 用途 | 99% 的业务表格与弹窗 | 树形表格（`TreeTable` 语义）、合并单元格、`DataGrid` 语义、完全自定义的浮层结构 |
| 门禁 | 正常放行 | 同样放行（仍走 `App*`，不回到原语） |
| 契约 | 全部 props / slots / 事件透传 | 同左 |

**使用示例**（两种典型形态）：

```vue
<!-- 标准分页表格：业务页只写列与数据 -->
<AppTable :value="rows" paginator :rows="20" striped-rows dataKey="id" :loading="loading">
  <Column field="standard_number" :header="t('standard_table.col_standard_number')" />
  <Column field="status" :header="t('standard_table.col_status')" />
  <template #empty><span>{{ t('common.no_data') }}</span></template>
</AppTable>

<!-- 高度定制：树形/合并单元格走 bare，零样式透传 -->
<AppTable bare :value="nodes" :expanded-rows="expanded" />

<!-- 弹窗：宽度语义原样保留，圆角/内边距由 AppDialog 承担 -->
<AppDialog v-model:visible="showAdd" :header="t('settings.users.add_title')" modal
           :style="{ width: '360px' }">
  <p>…</p>
  <template #footer>
    <AppButton type="ghost" :label="t('common.cancel')" @click="showAdd = false" />
    <AppButton type="primary" :label="t('common.save')" @click="save" />
  </template>
</AppDialog>
```

- 两个组件都必须 `defineOptions({ name: 'AppTable' / 'AppDialog' })`（G-027 门禁）；
- 全部 `$attrs` 透传是**硬契约**：替换存量时 `:style` 宽度、`@hide`、`v-model:visible`、
  `headerStyle`、`selectionMode`、可编辑单元格等语义必须原样保留，不允许在封装层「顺手归一」；
- `AppDialog` 的 header/content/footer 左右内边距必须同源（见 12.2），否则标题与正文错位。

### 12.5 门禁

新增 ESLint 规则 **`custom/no-raw-table`**：

| 项 | 值 |
|---|---|
| 级别 | **`error`**（模块二替换完成后已升级；`36` 处存量归零） |
| 覆盖 | `src/**/*.{ts,vue}`，模板标签 + 脚本 import 两侧 |
| 模板拦截 | 原生 `<table>`；PrimeVue `<DataTable>` / `<TreeTable>` / `<DataGrid>` / `<Dialog>` / `<ConfirmDialog>` / `<DynamicDialog>`（含 `Prime*` 前缀别名） |
| 脚本拦截 | `primevue/datatable`、`primevue/treetable`、`primevue/datagrid`、`primevue/dialog`、`primevue/confirmdialog`、`primevue/dynamicdialog` |
| 豁免 | `src/components/ui/App*.vue`（封装点）、`src/main.ts`（PrimeVue 全局注册点）、`*.test.ts` / `*.spec.ts` / `*.test.js` / `*.spec.js` / `*.test.vue`、路径含 `/e2e/` |
| 单测 | `eslint-plugin-custom/rules/no-raw-table.test.js`（RuleTester，22 例） |

**存量基线（2026-11-22，warn 落地时）**：`36` 处命中、分布在 `17` 个文件。下表是**落地快照**，
仅用于核对历史进度；**当前已全部归零**（见 12.6 交付台账）：

| 控件类型 | 命中 | 涉及文件 |
|---|---:|---:|
| PrimeVue `<DataTable>`（模板） | 10 | 9 |
| PrimeVue `<Dialog>`（模板） | 7 | 5 |
| `import 'primevue/datatable'` | 7 | 7 |
| 原生 `<table>`（手写数据表） | 6 | 5 |
| `import 'primevue/dialog'` | 4 | 4 |
| PrimeVue `<ConfirmDialog>`（模板） | 1 | 1 |
| `import 'primevue/confirmdialog'` | 1 | 1 |
| **合计** | **36** | **17** |

> 实现要点（实测，与 `no-raw-button` / `no-raw-input` 完全一致）：ESLint 10 + `vue-eslint-parser`
> 下直接写 `VElement` 访问器**不会触发**，必须经 `eslint-plugin-vue` 的 `defineTemplateBodyVisitor`
> 才能遍历模板；该包只提供 `dist/index.js`（无 `lib/utils` 子路径），其 utils 是 CommonJS，
> **ESM 命名导入拿不到函数（实测 undefined）**，故写
> `import vueUtils from 'eslint-plugin-vue/dist/utils/index.js'` 再解构
> `vueUtils.default.defineTemplateBodyVisitor`。
>
> **2026-11-22 升级实录**：探针文件 `src/views/__GateProbe2.vue` 同时含原生 `<table>`、
> PrimeVue `<DataTable>`、PrimeVue `<Dialog>` 与两个 `primevue/*` import → `lint` 报 **5 error**、
> exit 1；删除后 `lint` 恢复 `0 error`、exit 0。

### 12.6 模块二交付台账（2026-11-22 完成）

**Web 端：`36` 处 → `0`**

| 批次 | 范围 | 主要替换 |
|---|---|---|
| B1 | `StandardTable` / `BackupView` / `QualityView` | 3 `AppTable`（含 12 个 `Column` 原样保留） |
| B2 | `SchedulerStatus` / `FavoritesView` / `DownloadImport` | 3 `AppTable`（含 Tag severity、操作按钮、error 渲染的 `#body` 插槽） |
| B3 | `AnnounceDetail` / `StandardsStatusView` | 2 `AppTable`（`selectionMode="multiple"` + `v-model:selection` + `editMode="cell"` + 3 个可编辑 `AppInput` 全部保留） |
| B4 | `TaskManager` / `ValidityConfig` / `NotificationLogsView` / `SettingsTabToken` / `SettingsTabUsers` | 7 `AppDialog`（含 `:visible`+`@hide` 与 `v-model:visible` 两种写法、7 处 `:style` 宽度语义） |
| B5 | `QueryHistory` / `DownloadQueue` / `NotificationLogsView`（2 处） / `ValidityConfig` / `AdapterStatusCard` | 6 处手写 `<table>` → `AppTable`（含 sticky 表头、`row-class` 动态行类、紧凑仪表盘样式） |
| — | `SettingsView` | `<ConfirmDialog>` → 新增 `AppConfirmDialog`（见下） |

**`AppConfirmDialog` 为什么单独封装**：`<ConfirmDialog>` 不是普通弹窗，而是
**PrimeVue ConfirmationService 的渲染宿主** —— 业务侧 `confirm.require({...})` 把请求推进服务队列，
再由这个**单例**渲染队列头。它没有 `v-model:visible`、没有默认插槽，换成 `AppDialog` 会直接切断
`confirm.require()` 链路（弹窗永不出现且不报错）。故新增薄封装，保留服务契约、只收敛视觉
（圆角/内边距/按钮层级与 `AppDialog` 一致）。

**替换过程中修掉的真实缺陷**：

1. **测试 stub 未随组件改名** —— 多处测试 `stubs: { DataTable: Stub }` / `{ Dialog: Stub }` 在模板
   改 `AppTable`/`AppDialog` 后不再命中，`findComponent` 恒为空、断言静默失效。逐个改为新键名。
2. **`shallowMount` 把 `AppTable` 整棵子树 stub 掉** —— 任何替身都会绕开 `<Column>` 的 `#body` 插槽，
   使 `channelLabel`/`eventLabel`/`errorTypeLabel` 等**真实翻译逻辑不再被执行**（等于把要测的东西测没了）。
   `NotificationLogsView.test.ts` 改为 `mount` + 真实 PrimeVue 插件，让 AppTable 走真实渲染路径。
3. **`NotificationConfig` 的「渲染总开关」用例 flake** —— 原用固定 `setTimeout(10)` 睡等，全量并行时
   jsdom 环境加载把这 10ms 挤爆 → 偶发 5s 超时（单跑必绿）。改为 `vi.waitFor()` 轮询，既消除 flake
   又不放宽断言。
4. **scoped 样式对 PrimeVue 渲染出的 `th`/`td` 不生效** —— `AdapterStatusCard` 的 `.adapter-table`
   原直接选 `th`/`td`，改 AppTable 后这些节点不带本组件 scope 属性，规则全部失效。改用 `:deep()`。

**Win 端**：`BaseTable` / `BaseDialog` 见 `docs/architecture/modules/ui.md`（模块二-C 交付）。

---

## 十三、阶段三：页面级布局（Layout / Card）

> 状态：**进行中**。规范（13.1–13.4）已定稿，`<PageContainer>` / `<AppCard>` 封装与存量替换
> 按 `views/` 分批推进。门禁 `custom/no-raw-card` 当前为 `warn`，替换完成后升 `error`。

### 13.1 PageContainer 规范

#### 13.1.1 职责边界（最容易踩的坑）

本仓有**两层**容器，分工必须分清，否则页面会被挤成很窄一条：

| 层 | 组件 | 负责 | 留白 |
|---|---|---|---|
| 视口级 | `AppLayout` 的 `.content-inner` | 内容区与浏览器窗口边缘的距离、`max-width:1600px` 居中 | 桌面 32/36、平板 24/20、移动 16/12 |
| 页面级 | `<PageContainer>` | 页面内块之间的垂直节奏、标题统一排版、本页自己的最大宽度 | **默认不加左右内边距** |

- **禁止两层同时加左右内边距** —— 会变成"左右各 36px + 各 32px"，内容区凭空少 136px；
- 子页确实需要自己的左右留白（如嵌在 Tab 里的表单页）时，用 `<PageContainer padded>` 显式开启，
  且档位与 `.content-inner` 同值；
- 全宽页面（仪表盘 grid）用 `<PageContainer flush>` 去掉一切内边距。

#### 13.1.2 三断点（与 `.content-inner` 同一断点，不许各自为政）

| 断点 | 条件 | `padded` 时的左右内边距 |
|---|---|---|
| 桌面 | `> 1023px` | `--space-32` |
| 平板 | `<= 1023px` | `--space-24` |
| 移动 | `<= 767px` | `--space-16` |

- 断点值必须与 `AppLayout.vue` 的 `@media` 完全一致，否则会出现「外层已切移动档、内层还是桌面档」的错位；
- 竖直节奏：桌面 `gap: --space-16`、移动 `gap: --space-12`。

#### 13.1.3 标题层级

`<PageContainer title="...">` 渲染 `h2.page-title`，统一样式为：

| 属性 | 值 |
|---|---|
| 字号 | `--font-size-20` |
| 字重 | `--font-weight-semibold` |
| 颜色 | `--text-heading` |
| 行高 | `--line-height-snug` |
| margin | `0`（间距由容器的 `gap` 承担，不再写 `margin-bottom`） |

- **背景**：迁移前 8 个 views（Backup / DownloadQueue / NotificationLogs / Quality / QueryHistory /
  SchedulerStatus / StandardsStatus / SystemResources）各自逐字重复了同一段 `.page-title` CSS，
  且 `.page` 的 `max-width` 各不相同（900 / 1000 / 1100）。统一到 `PageContainer` 的
  `title` + `maxWidth` 两个 prop 后，这 8 段重复 CSS 全部删除；
- 标题右侧操作区用 `#actions` 插槽（自动 `flex-shrink: 0`，移动端换行到标题下方）；
- 需要完全自定义标题（如带面包屑）时用 `#title` 插槽接管，此时 `title` prop 不生效。

### 13.2 Card 规范

| 属性 | 默认 | `elevated` |
|---|---|---|
| 阴影 | `--shadow-sm` | `--shadow-md` |
| 圆角 | `--ds-radius-md` | 同左 |
| 边框 | `1px solid var(--border)` | 同左 |
| 内容区内边距 | `--space-20` | 同左 |
| 标题区 | `--space-16 / --space-20` + 底部分隔线 | 同左 |
| 页脚区 | `--space-12 / --space-20` + 顶部分隔线 | 同左 |

- **只有两档阴影**：`--shadow-sm`（默认，卡片浮起一点点）与 `--shadow-md`（`elevated`，需要与背景
  明显分离的浮层式卡片）。**不引入第三档** —— 三档以上的阴影在浅色主题下几乎无法分辨，
  只会让规范失去约束力；
- 圆角与按钮/输入框/表格统一到 `--ds-radius-md`，不再出现 `--radius-lg`（14px）的卡片；
- 有标题时内容区上内边距收一档（`--space-16`），因为标题区已有自己的下边距与分隔线，
  否则会出现"标题分隔线下面空一大块"的视觉断层；
- 仪表盘这类需要完全自定义卡片结构（渐变底、图标方块、自定义间距）的场景用 `<AppCard bare>`。

### 13.3 禁止项

- **禁止业务代码直接使用 PrimeVue `<Card>`**：一律用 `<AppCard>`；需要自定义结构用 `<AppCard bare>`；
- **禁止直接 `import 'primevue/card'`**；
- **禁止在 views 的外层 div 自写 `padding` / `margin` / `max-width`**：统一走
  `<PageContainer>` 的 `padded` / `flush` / `maxWidth` prop。页面只允许写**内部布局**
  （栅格、flex、gap），不写容器级留白；
- **禁止再写 `.page-title` 的重复定义**：标题样式由 `PageContainer` 统一提供。

### 13.4 组件契约

| 组件 | 底层 | 显式 props | 透传 | slots |
|---|---|---|---|---|
| `PageContainer` | 原生 `div`（无第三方依赖） | `maxWidth`（`number`/`string`/`null`，数字自动补 px）、`title`、`subtitle`、`flush`、`padded` | `$attrs` 全量透传到根元素 | 默认、`#title`（接管标题区）、`#actions`（标题右侧操作区） |
| `AppCard` | PrimeVue `Card` | `elevated`、`bare` | `$attrs` 全量透传（`class`/`style`/`data-*`/`aria-*`），业务 class 与 DS class 合并 | `v-for` 动态全量转发（`#header`/`#title`/`#subtitle`/`#content`/`#footer` 及任何未列举的具名插槽） |

- 两个逃生舱：
  - `PageContainer` 的 `flush`（全宽）/ `padded`（显式左右留白）—— 解决"默认不加左右内边距"带来的
    两种例外；
  - `AppCard` 的 `bare` —— 走 PrimeVue 官方 `:unstyled`，零基础视觉，外观由宿主全权负责；
- **不是绕过门禁的手段**：`bare` / `flush` 仍必须走 DS 组件，只是视觉归宿主。

### 13.5 门禁

新增 ESLint 规则 **`custom/no-raw-card`**：

| 项 | 值 |
|---|---|
| 级别 | **`error`**（模块三替换完成后已升级；`29` 处存量归零） |
| 覆盖 | `src/**/*.{ts,vue}`，模板标签 + 脚本 import 两侧 |
| 模板拦截 | PrimeVue `<Card>`（含 `PrimeCard` 前缀别名） |
| 脚本拦截 | `primevue/card` |
| 豁免 | `src/components/ui/App*.vue`（封装点）、`src/main.ts`（PrimeVue 全局注册点）、`*.test.ts` / `*.spec.ts` / `*.test.js` / `*.spec.js` / `*.test.vue`、路径含 `/e2e/` |
| 单测 | `eslint-plugin-custom/rules/no-raw-card.test.js`（RuleTester，9 例） |

**存量基线（2026-11-22，warn 落地时）**：`29` 处命中（`<Card>` 20 处 + `import 'primevue/card'` 9 处），
分布在 `15` 个文件。该表是**落地快照**，仅用于核对历史进度；**当前已全部归零**（见 13.6）。

> **2026-11-22 升级实录**：探针文件 `src/views/__GateProbe3.vue` 同时含 PrimeVue `<Card>` 模板
> 与 `import 'primevue/card'` → `lint` 报 **2 error**、exit 1；删除后 `lint` 恢复 `0 error`、exit 0。

### 13.6 模块三交付台账（2026-11-22 完成）

**Web 端：`29` 处 → `0`**

| 批次 | 范围 | 主要替换 |
|---|---|---|
| 容器 | `BackupView` / `DownloadQueue` / `NotificationLogsView` / `QualityView` / `QueryHistory` / `SchedulerStatus` / `StandardsStatusView` / `SystemResources` | 8 个 `<div class="page">` + `<h2 class="page-title">` → `<PageContainer :max-width :title>`；**同时删除 8 段逐字重复的 `.page` / `.page-title` CSS** |
| 卡片 | 上述 8 页 + `AnnounceDetail`（2）+ `DownloadImport`（6） | 20 处 `<Card>` → `<AppCard>` |

**保留原结构的位置与理由**（这三类不套 `PageContainer`）：

| 页面 | 结构 | 理由 |
|---|---|---|
| `HomeView` | `<div class="dashboard-container">` + GridLayout | 仪表盘是栅格拖拽布局，容器需要占满视口且不能有 max-width / gap；套 `PageContainer` 会破坏 GridLayout 的尺寸计算 |
| `LoginView` / `RegisterView` | `<div class="login-page">` 居中登录卡 | 全屏居中布局，不参与 `.content-inner` 的常规留白体系（登录页在 `App.vue` 里就绕过了 `AppLayout`） |
| `ForbiddenView` / `LegacyRedirect` | 状态页居中 div | 单行状态提示，无标题/无内容块，套容器只会增加无意义的 DOM 层 |

**替换过程中修掉的真实缺陷**：

1. **8 段重复 CSS** —— `.page-title` 在 8 个 views 里逐字重复（`margin: 0 0 --space-20` + 20px/600/`--text-heading`），
   `.page` 的 `max-width` 却各不相同（900/1000/1100）。统一到 `PageContainer` 的 `title` + `maxWidth`
   后全部删除，`max-width` 变成每页显式声明的 prop（可读性也更好）。
2. **测试 stub 未随组件改名** —— 5 个测试文件 `stubs: { Card: StubCard }` 在模板改 `AppCard` 后不再命中，
   标题/卡片内容不渲染、断言全红。逐个补 `AppCard` / `PageContainer` 替身。
3. **`SystemResources.test.ts` 的 `findAllComponents(StubCard)`** —— 断言数「3 张卡片」，改 AppCard 后
   必须改查 `StubAppCard`，否则恒为 0。这类「断言目标与 stub 绑定」的失败最容易被误读成组件 bug。

---

## 十四、阶段三：微交互（Toast / Loading / 过渡动画）

> 状态：**已完成**（2026-11-23）。三条门禁 `custom/no-raw-toast` 已升 `error`。

### 14.1 Toast 提示

#### 14.1.1 为什么是「composable + 宿主」两件套

PrimeVue 的 Toast 是**运行时服务**：`<Toast />` 只是渲染宿主，真正的 API 是 `useToast()`
返回的 `toast.add({...})`。而 `useToast()` 内部 `inject(PrimeVueToastSymbol)`，**必须在
`setup()` 同步调用**，不能在异步回调或普通函数里临时调。

因此统一 Toast 必须是两件套：

| 件 | 文件 | 职责 |
|---|---|---|
| 服务 | `web/src/composables/useAppToast.ts` | 收口 add() 口径：severity 白名单、默认 life、文案与 i18n 插值、group 语义 |
| 宿主 | `web/src/components/ui/AppToast.vue` | 只负责渲染（位置/圆角/阴影/语义色/进出场动画） |

宿主挂在 `App.vue`（全站唯一一份），业务页**不得**再写 `<Toast />`。

#### 14.1.2 两种消费方式

```ts
// A. 组件内（有 setup 上下文）
import { useAppToast } from '@/composables/useAppToast'
const notify = useAppToast()
notify.success('已保存')
notify.error({ key: 'sites.load_failed', detail: t('common.check_network') })

// B. 非组件模块（composables / api 层）—— 走全局单例
import { appToast } from '@/composables/useAppToast'
appToast.error({ summary: message })
```

`appToast` 的全局实例由 `App.vue` 挂载时 `bindAppToast(useToast())` 注入；
未绑定前调用会 `console.warn` 并**静默丢弃**（不抛错 —— 提示失败不该拖垮业务）。

#### 14.1.3 口径（与直接 `toast.add()` 的差异）

| 项 | 规则 |
|---|---|
| `severity` | 只允许 `success` / `info` / `warn` / `error`（与 DS 语义色一一对应，**不自创第五种**） |
| 默认 `life` | `success`/`info` → **2000ms**；`warn`/`error` → **3000ms**（错误停留更久，让用户看清） |
| `closable` | 统一 `false`（提示自动消失，不给用户额外关闭负担） |
| 文案 | `summary` 或 `key`（key 优先，交给全局 i18n 实例翻译）；`detail` / `detailKey` 同理；`named` 传插值参数 |
| `group` | **只在"同一实体反复失败"场景用**（如按站点分组）。PrimeVue 的 group 语义是"替换同组"，滥用会让多条提示互相覆盖 |
| 空文案 | 跳过并 `console.warn`（调用方的 bug，但不抛错） |

#### 14.1.4 视觉口径

| 属性 | 值 |
|---|---|
| 位置 | `top-right`（与 DS 的"页面右上操作区"视线一致） |
| 背景 | 实色语义底：success `--success` / info `--info` / warn `--warn-text` / error `--danger` |
| 文字 | `--text-on-primary`（白字） |
| 圆角 | `--ds-radius-md` |
| 阴影 | `--shadow-md`（浮层，需与内容明显分离） |
| 进出场 | 从右滑入 16px → 0，150ms（与页面过渡同源） |

### 14.2 加载态（Loading）

#### 14.2.1 三种形态

| `variant` | 用途 | 典型场景 |
|---|---|---|
| `spinner`（默认） | **短时**操作（<1s） | 按钮触发的保存、单次请求 |
| `skeleton` | **列表/卡片首屏**（>1s 取数） | 仪表盘卡片、表格首次加载 |
| `inline` | **内嵌**在表格/区块内 | 筛选栏旁的小提示 |

**选择判据**：加载态的价值在于「不让用户以为页面卡死」与「加载完成后不跳动」。
- 短时 → spinner（骨架屏来不及显示就消失了，反而闪一下）；
- 首屏 → skeleton（占位尺寸接近真实内容，避免加载完成时布局跳动）；
- 内嵌 → inline（不打断已有布局）。

#### 14.2.2 口径

| 项 | 规则 |
|---|---|
| 尺寸 | `size` = `l` / `m` / `s`，圆环直径与描边宽全部取令牌（`--size-14/20/24`） |
| 骨架条数 | `rows`（默认 3）—— 按实际列表行数传，否则占位与真实内容高度差太多 |
| 骨架高度 | `rowHeight` = `s`/`m`/`l`（映射 `--size-8/12/16`）或数字 px |
| 无障碍 | 所有形态带 `role="status"` + `aria-live="polite"`；骨架屏额外有 sr-only 文案供读屏 |
| 动效偏好 | `prefers-reduced-motion: reduce` 时关掉旋转与 shimmer（避免前庭不适） |

#### 14.2.3 为什么不用 PrimeVue 的 ProgressSpinner

它的尺寸/颜色只能靠 CSS 字面量覆盖（PrimeVue 4.5.5 的 ProgressSpinner **没有 size prop**，
见 A-51 的实测记录），而 DS 要求所有尺寸取令牌。本组件用纯 CSS 圆环 + 令牌，
既满足 G-055（无字面量）又便于统一。

#### 14.2.4 例外：网格骨架

`StatsCard` 的骨架是**两栏网格**（1 主块 + 3 副块，`grid-column` 定位），
而 `AppLoading` 的骨架是**竖排列表**。换成通用骨架会丢掉网格占位，
加载完成时卡片高度与位置都会跳动，**反而劣化体验**。
故该卡片保留自有骨架结构，只把渐变动画与圆角令牌口径对齐 `AppLoading`
（避免两套 shimmer 实现）。**这是有意例外，不是漏改。**

### 14.3 过渡动画

#### 14.3.1 页面切换（全站唯一）

定义在 `App.vue` 的 `<style>`（非 scoped），类名 `.page`：

| 阶段 | 时长 | 变化 |
|---|---|---|
| 进入 | 150ms | `opacity 0→1`、`translateY(8px→0)` |
| 离开 | 100ms | `opacity 1→0`、`translateY(0→-4px)` |

- **必须用 `mode="out-in"`**：默认并行会让两个页面同时存在并重叠，视觉上是"双页闪一下"；
- 位移幅度刻意小（8px / -4px），避免页面大幅晃动；
- 离开比进入快（100ms < 150ms），减少"卡住"感；
- **业务页不得再自写 `.page` 过渡**；需要特殊过渡的走 `<Transition name="...">` 并在本节登记。

#### 14.3.2 折叠展开（`.collapsible`）

全站唯一实现在 `views/settings/shared.css`：

- 曲线与时长与 DS 的 `--transition` 同源（0.2s ease）；
- `max-height` 必须给"足够大的上界"（当前 2000px）—— CSS 无法对 `auto` 高度做过渡，
  过渡按声明值线性插值，上界过大会让动画变慢。面板内容显著变长时需同步调大；
- 进出场都保留 `overflow: hidden`，否则折叠中途内容会溢出。

**背景**：迁移前 `NotificationConfig.vue` 有一份本地副本且**曲线不同**（多 padding 过渡），
导致同一交互在 settings 子页与通知配置页观感不一致。已删除本地副本，统一到 `shared.css`。

#### 14.3.3 其他过渡

| 类名 | 位置 | 用途 |
|---|---|---|
| `.menu-fade` | `AppLayout.vue` | 浮动工作台菜单展开 |
| `.announce-fade` | `RecentAnnounceCard.vue` | 公告列表刷新 |

新增过渡前先检查本节是否已有可复用的类；**不要为一次性效果新增全局类**。

### 14.4 门禁

| 规则 | 拦截对象 | 级别 |
|---|---|---|
| `custom/no-raw-toast` | 模板 `<Toast>` / `<PrimeToast>`；脚本 `import 'primevue/toast'`、`'primevue/usetoast'` | **`error`** |

豁免：`src/components/ui/App*.vue`（封装点）、`src/composables/useAppToast.ts`（服务封装点）、
`src/App.vue`（宿主挂载 + 全局绑定）、`src/main.ts`（PrimeVue 全局注册）、
`*.test.ts` / `*.spec.ts`、路径含 `/e2e/`。

> **2026-11-23 升级实录**：探针文件 `src/views/__GateProbe4.vue` 同时含
> `import 'primevue/toast'`、`import 'primevue/usetoast'`、`<Toast />` → `lint` 报 **3 error**、
> exit 1；删除后 `lint` 恢复 `0 error`、exit 0。

### 14.5 验收清单

- [x] `useAppToast` composable + `AppToast` 宿主 + 单测
- [x] `AppLoading`（spinner/skeleton/inline 三形态）+ 单测
- [x] 全站 Toast 收口：`useToast` 从 10 处降至 **0**（业务代码），`toast.add()` 23 处 → **0**
- [x] 全站 Loading 收口：`ProgressSpinner` 6 处 → **0**；文本占位 2 处 → `AppLoading skeleton`
- [x] 页面过渡统一（`mode="out-in"` + 减少动效偏好）
- [x] `collapsible` 过渡去重（删除 NotificationConfig 本地副本）
- [x] `custom/no-raw-toast` 升 `error`（反证 3 error / exit 1）
