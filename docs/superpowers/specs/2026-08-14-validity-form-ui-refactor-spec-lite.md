# 时效性检查配置表单 UI 重构 spec-lite

> 日期：2026-08-14 | 类型：功能开发（前端 UI 重构）

## 用户指令摘要

- 修复运行时错误 `can't access property "data", e is null`（进入/切换「首次执行」时触发）
- 修复「首次执行（周几）」高度过高（42px，纵向双箭头撑高）、字段宽度不一、时间与总周期视觉重叠
- 时间选择器废除「双输入框+独立 Spinner」，改为单入口只读框 → 点击弹面板选 HH:mm

## 采纳的关键设计决策

1. 周几：`WeekdaySelector`（纵向双箭头）→ `PrimeVue Select` 下拉，直接绑定 `config.first_weekday`（number 1-7）
2. 时间：`TimeInput`（双 InputNumber showButtons）→ `PrimeVue DatePicker` `timeOnly` + `hourFormat="24"`，computed 桥接 `Date`↔`'03:00'` string
3. 总周期：保持 `InputNumber`（保留 min=4/max=52 步进约束），仅统一高度样式
4. 布局：`.form-grid` 增大 gap、`align-items:end` 底部对齐；字段控件统一高度 36px、宽度撑满列宽（保留响应式，不硬编码 140px）
5. 删除 `TimeInput.vue`、`WeekdaySelector.vue`（已 grep 确认全代码库仅 `ValidityConfig.vue` 引用）

## 识别到的风险点及与现有架构的冲突

1. **DatePicker timeOnly 面板是箭头式（▲▼+输入）非滚轮**，验收「鼠标滚轮平滑滚动」不满足，需与用户对齐
2. DatePicker `modelValue` 是 `Date` 对象，后端存 `'03:00'` string，computed 转换需防 null/undefined
3. 现有 `ValidityConfig.test.ts` 在 jsdom 下 mount，`DatePicker` 可能依赖浏览器 API，需实测
4. 删除组件前需二次 grep 确认无 `--deselect`/`collect_ignore` 等隐藏引用

## 验证方式

- `cd web && npm run test -- ValidityConfig` 全通过
- `cd web && npm run build`（含 vue-tsc 类型检查）零错误
- 手动：三字段高度一致（36px）、无重叠、时间面板点击弹出、输入框旁无按钮、切换/清空不报错
