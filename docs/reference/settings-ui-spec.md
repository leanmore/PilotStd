# Settings 页面 UI 组件开发规范

> 沉淀自 2026-08-05 界面设置布局错乱根因调查（P0-P2 修复）。

---

## 1. 架构层级

```
SettingsView.vue           ← 编排层：标签页导航、配置读写、provide 注入
  ├─ SettingsTabSchema.vue ← Schema 驱动通用渲染器（storage/network/query/scan/ocr）
  ├─ SettingsTabAppearanceMixed.vue ← 混合布局（手写 Grid + Pinia store）
  ├─ SettingsTabSites.vue  ← 独立 API Tab
  ├─ ...其他独立 Tab
  └─ DynamicSettingField.vue ← Schema 字段原子渲染器（display:contents）
```

---

## 2. 表单网格布局规范

### 2.1 基础结构

Setting Tab 内所有表单行必须使用 `.form-grid` 容器：

```css
.form-grid {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 14px 20px;
  align-items: start;
}
```

### 2.2 标签选择器：只用直系子级

```css
/* ✅ 正确 — 仅匹配 .form-grid 的直接子 <label> */
.form-grid > label {
  color: var(--text-dim);
  font-weight: 500;
  padding-top: 9px;
}

/* ❌ 错误 — 后代选择器会污染嵌套子组件中的 <label> */
.form-grid label { ... }
```

**设计原因**：`.theme-option`、`.upload-btn` 等组件内部使用 `<label>` 元素，后代选择器会意外覆盖其样式。`display:contents` 穿透的场景（DynamicSettingField）由组件自身 scoped 样式覆盖。

### 2.3 分组标题：fieldset-label + fieldset-gap

当 Tab 内容有多个逻辑分组时，必须使用分组标题而非普通 `<label>`：

```html
<!-- ✅ 正确 — 分组标题跨两列，上方有间距 -->
<div class="fieldset-gap" />
<div class="fieldset-label">主题</div>
<div class="theme-options" style="grid-column: 1 / -1">
  <!-- 分组内容 -->
</div>

<!-- ❌ 错误 — 普通 label 只有 160px 宽，视觉上孤立 -->
<label>主题</label>
<div class="theme-options">...</div>
```

对应 CSS：

```css
.fieldset-gap   { grid-column: 1 / -1; height: 12px; }
.fieldset-label { grid-column: 1 / -1; font-weight: 700; color: var(--text-heading); font-size: 14px; }
```

### 2.4 辅助文字对齐

帮助文本/错误提示必须指定 `grid-column: 2`，避免占据 label 列：

```html
<!-- ✅ 正确 -->
<span class="text-dim" style="grid-column:2">支持手动上传图片或填入 API 网络地址</span>

<!-- ❌ 错误 — 默认占 col 1，与 label 列重叠 -->
<span class="text-dim">支持手动上传图片或填入 API 网络地址</span>
```

---

## 3. 样式导入规范

### 3.1 禁止 @import 含全局类名的样式文件

```html
<!-- ❌ 禁止 -->
<style scoped>
@import '@/views/settings/shared.css';  /* .card, .form-grid 等与全局 style.css 重复 */
</style>

<!-- ✅ 正确：将共享样式提升为全局 CSS（style.css），组件只写自身特有样式 -->
<style scoped>
.my-tab-special { ... }
</style>
```

**设计原因**：`@import` 在 `<style scoped>` 中会为导入规则注入 `[data-v-xxx]`，与全局同名类产生两套并行定义。修改任一处容易遗漏另一处，造成视觉不一致。

**当前状态（历史债务）**：10 个 Settings 子组件通过 `@import './shared.css'` 导入共享样式。此债务已通过注释标注，后续新增 Tab 不再照搬此模式，改为直接依赖 `style.css` 全局定义 + 组件自身 scoped 样式。

### 3.2 全局样式依赖清单

修改 `style.css` 中的 `.card` / `.card-header` / `.form-grid` 等全局定义时，必须检查注释中列出的依赖文件清单：

```css
/*
 * 已知依赖此全局定义的文件：
 *   PendingView.vue, TaskView.vue, OrganizeView.vue, NotificationLogsView.vue
 */
```

新增依赖文件时，必须同步更新此清单。

---

## 4. 新增 Settings Tab 标准流程

1. **判断类型**：纯表单字段 → 走 Schema（后端定义字段）；混合布局 → 手写组件
2. **创建组件**：`web/src/views/settings/SettingsTabXxx.vue`
3. **注册路由**：在 `SettingsView.vue` 的 `tabComponentMap` 中注册
4. **翻译键**：在 `locales/` 中添加 `settings.tabs.xxx` 和字段级翻译
5. **使用 .form-grid**：所有表单行放入 `.form-grid` 容器
6. **分组用 fieldset-label**：多分组场景必须使用分组标题
7. **标签用 > 选择器**：确认 `shared.css` 的 `.form-grid > label` 正确匹配
8. **不 @import shared.css**：组件自身写 scoped 样式，不导入共享样式文件

---

## 5. 组件语义规范

| 场景 | 使用元素 | 必要属性 |
|------|---------|---------|
| 表单行标签 | `<label for="...">` | `for` 指向控件 `id` |
| 分组标题 | `<div class="fieldset-label">` | — |
| 单选卡片组 | `<div role="radio">` | `aria-checked`, `tabindex="0"`, `@keydown.enter/space` |
| 上传按钮 | `<label class="upload-btn">` 包裹 `<input type="file" hidden>` | — |

---

## 6. 常见反模式

| 反模式 | 后果 | 正确做法 |
|--------|------|---------|
| 分组标题用 `<label>` | 160px 窄列内孤立悬浮，与内容断裂 | 用 `.fieldset-label` |
| `.form-grid label` 后代选择器 | 污染嵌套 `<label>` 子组件 | 用 `.form-grid > label` |
| 帮助文字不指定 grid-column | 占据 label 列，col 2 空置 | 加 `grid-column:2` |
| 区块间无 fieldset-gap | 内容拥挤堆叠，无视觉层级 | 分组前插入 `.fieldset-gap` |
| `<style scoped>` 内 `@import` 全局类名文件 | 双源定义，修改易遗漏 | 提升到全局 CSS 或组件内联 |
| 可交互卡片用 `<label>` | 语义错误，无键盘可访问性 | 用 `div[role=radio]` + 键盘事件 |

---

## 7. 响应式断点

统一断点：**768px**。全局 `style.css` 和 Settings `shared.css` 已对齐。

```css
@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr; }
}
```

禁止在响应式规则中使用 `!important`，避免阻断组件级样式覆盖。
